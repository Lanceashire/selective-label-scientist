use keyring::Entry;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{
    collections::HashMap,
    env, fs,
    fs::OpenOptions,
    io::{BufRead, BufReader, Read, Write},
    path::PathBuf,
    process::{Child, ChildStdin, Command, Stdio},
    sync::{
        atomic::{AtomicBool, AtomicU64, Ordering},
        mpsc, Arc, Mutex, OnceLock,
    },
    thread,
    time::{Duration, Instant},
};
use tauri::{AppHandle, Emitter, Manager, Runtime};

const SERVICE: &str = "ECOMIC Desktop";
static RUNTIME_DIR: OnceLock<PathBuf> = OnceLock::new();
static DIAGNOSTIC_LOG_DIR: OnceLock<PathBuf> = OnceLock::new();
static REQUEST_SEQUENCE: AtomicU64 = AtomicU64::new(1);
static TASK_SEQUENCE: AtomicU64 = AtomicU64::new(1);
const CREATE_NO_WINDOW: u32 = 0x08000000;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
const MAX_JSONL_LINE_BYTES: u64 = 4 * 1024 * 1024;

enum SidecarFrame {
    Response(Result<Value, String>),
    Event(Value),
}

struct Sidecar {
    child: Mutex<Child>,
    stdin: Mutex<ChildStdin>,
    pending: Mutex<HashMap<String, mpsc::Sender<SidecarFrame>>>,
    healthy: AtomicBool,
}

#[derive(Clone)]
struct Bridge(Arc<Mutex<Option<Arc<Sidecar>>>>);

struct ScientistTask {
    session_id: String,
    status: Mutex<String>,
    child: Mutex<Option<Child>>,
}
#[derive(Clone)]
struct TaskManager(Arc<Mutex<HashMap<String, Arc<ScientistTask>>>>);

fn task_id() -> String {
    format!("task_{}", TASK_SEQUENCE.fetch_add(1, Ordering::Relaxed))
}
fn task_status(task: &ScientistTask) -> String {
    task.status
        .lock()
        .map(|value| value.clone())
        .unwrap_or_else(|_| "ERROR".into())
}
fn set_task_status(task: &ScientistTask, status: &str) {
    if let Ok(mut value) = task.status.lock() {
        *value = status.into();
    }
}

impl Sidecar {
    fn terminate(&self) {
        if let Ok(mut child) = self.child.lock() {
            if child.try_wait().ok().flatten().is_none() {
                terminate_process_tree(&mut child);
            }
        }
    }
}

impl Drop for Sidecar {
    fn drop(&mut self) {
        self.terminate();
    }
}
#[derive(Clone, Deserialize, Serialize)]
struct Profile {
    provider: String,
    label: String,
    model_id: String,
    base_url: Option<String>,
    tool_calling_verified: bool,
    last_connection_test: Option<String>,
}
#[derive(Default, Deserialize, Serialize)]
struct Store {
    default_provider: Option<String>,
    profiles: Vec<Profile>,
}

fn root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .and_then(|p| p.parent())
        .expect("desktop layout")
        .to_path_buf()
}
fn label(p: &str) -> Option<&'static str> {
    match p {
        "openai" => Some("OpenAI"),
        "anthropic" => Some("Anthropic"),
        "deepseek" => Some("DeepSeek"),
        "google" => Some("Google Gemini"),
        "openrouter" => Some("OpenRouter"),
        "moonshot" => Some("Moonshot"),
        "qwen" => Some("Qwen"),
        "minimax" => Some("MiniMax"),
        "custom_openai_compatible" => Some("Custom OpenAI-Compatible"),
        _ => None,
    }
}
fn key_env(p: &str) -> Option<&'static str> {
    match p {
        "openai" => Some("OPENAI_API_KEY"),
        "anthropic" => Some("ANTHROPIC_API_KEY"),
        "deepseek" => Some("DEEPSEEK_API_KEY"),
        "google" => Some("GEMINI_API_KEY"),
        "openrouter" => Some("OPENROUTER_API_KEY"),
        "moonshot" => Some("MOONSHOT_API_KEY"),
        "qwen" => Some("QWEN_TOKEN_PLAN_CN_API_KEY"),
        "minimax" => Some("MINIMAX_API_KEY"),
        "custom_openai_compatible" => Some("ECOMIC_CUSTOM_API_KEY"),
        _ => None,
    }
}
fn catalog() -> Vec<Value> {
    [("openai","OpenAI",false),("anthropic","Anthropic",false),("deepseek","DeepSeek",false),("google","Google Gemini",false),("openrouter","OpenRouter",false),("moonshot","Moonshot",false),("qwen","Qwen",false),("minimax","MiniMax",false),("custom_openai_compatible","Custom OpenAI-Compatible",true)].into_iter().map(|(id,label,requires_base_url)| json!({"id":id,"label":label,"requires_base_url":requires_base_url})).collect()
}

fn runtime_dir() -> PathBuf {
    RUNTIME_DIR
        .get()
        .cloned()
        .unwrap_or_else(|| root().join("release/runtime/ecomic-agent"))
}
fn backend_executable() -> PathBuf {
    env::var_os("ECOMIC_BACKEND")
        .map(PathBuf::from)
        .unwrap_or_else(|| runtime_dir().join("ecomic-backend.exe"))
}
fn node_executable() -> PathBuf {
    env::var_os("ECOMIC_NODE")
        .map(PathBuf::from)
        .unwrap_or_else(|| runtime_dir().join("node.exe"))
}
fn next_request_id() -> String {
    format!("req_{}", REQUEST_SEQUENCE.fetch_add(1, Ordering::Relaxed))
}
fn redact_after_marker(mut value: String, marker: &str) -> String {
    if let Some(start) = value
        .to_ascii_lowercase()
        .find(&marker.to_ascii_lowercase())
    {
        let secret_start = start + marker.len();
        let secret_end = value[secret_start..]
            .find(|character: char| {
                character.is_whitespace() || matches!(character, '"' | '\'' | ',' | ';')
            })
            .map(|offset| secret_start + offset)
            .unwrap_or(value.len());
        if secret_end > secret_start {
            value.replace_range(secret_start..secret_end, "[REDACTED]");
        }
    }
    value
}

fn redact_diagnostic(event: &str) -> String {
    let mut safe = event.to_owned();
    for marker in [
        "authorization:",
        "bearer ",
        "openai_api_key=",
        "anthropic_api_key=",
        "deepseek_api_key=",
        "gemini_api_key=",
        "openrouter_api_key=",
        "moonshot_api_key=",
        "qwen_token_plan_cn_api_key=",
        "minimax_api_key=",
        "ecomic_custom_api_key=",
    ] {
        safe = redact_after_marker(safe, marker);
    }
    safe
}

fn append_diagnostic(event: &str) {
    if let Some(directory) = DIAGNOSTIC_LOG_DIR.get() {
        let _ = fs::create_dir_all(directory);
        let path = directory.join("ecomic-desktop.log");
        if fs::metadata(&path)
            .map(|item| item.len() > 2 * 1024 * 1024)
            .unwrap_or(false)
        {
            let rotated = directory.join(format!("ecomic-desktop-{}.log", chrono_like_timestamp()));
            let _ = fs::rename(&path, rotated);
        }
        if let Ok(mut file) = OpenOptions::new().create(true).append(true).open(path) {
            let _ = writeln!(
                file,
                "{} {}",
                chrono_like_timestamp(),
                redact_diagnostic(event)
            );
        }
    }
}

fn drain_stderr(component: &'static str, stderr: impl Read + Send + 'static) {
    thread::spawn(move || {
        for line in BufReader::new(stderr).lines().map_while(Result::ok) {
            append_diagnostic(&format!("{} stderr: {}", component, line));
        }
    });
}
fn chrono_like_timestamp() -> u128 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|value| value.as_millis())
        .unwrap_or(0)
}

fn response_error(response: &Value) -> String {
    let error = response.get("error").and_then(Value::as_object);
    let code = error
        .and_then(|item| item.get("code"))
        .and_then(Value::as_str)
        .unwrap_or("BACKEND_ERROR");
    let message = error
        .and_then(|item| item.get("message"))
        .and_then(Value::as_str)
        .unwrap_or("Backend request failed.");
    format!("{}: {}", code, message)
}

fn fail_pending(sidecar: &Sidecar, message: &str) {
    if let Ok(mut pending) = sidecar.pending.lock() {
        for (_, sender) in std::mem::take(&mut *pending) {
            let _ = sender.send(SidecarFrame::Response(Err(message.into())));
        }
    }
}

fn spawn() -> Result<Arc<Sidecar>, String> {
    let backend = backend_executable();
    if !backend.is_file() {
        return Err("bundled backend executable is unavailable".into());
    }
    let mut command = Command::new(backend);
    command
        .current_dir(runtime_dir())
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    let mut child = command.spawn().map_err(|_| "backend start failed")?;
    let stdin = child.stdin.take().ok_or("backend stdin unavailable")?;
    let stdout = child.stdout.take().ok_or("backend stdout unavailable")?;
    let stderr = child.stderr.take().ok_or("backend stderr unavailable")?;
    drain_stderr("backend", stderr);
    let sidecar = Arc::new(Sidecar {
        child: Mutex::new(child),
        stdin: Mutex::new(stdin),
        pending: Mutex::new(HashMap::new()),
        healthy: AtomicBool::new(true),
    });
    let reader_sidecar = Arc::clone(&sidecar);
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut bytes = Vec::new();
            let read = reader
                .by_ref()
                .take(MAX_JSONL_LINE_BYTES + 1)
                .read_until(b'\n', &mut bytes);
            let count = match read {
                Ok(value) => value,
                Err(_) => {
                    append_diagnostic("backend response stream failed");
                    reader_sidecar.healthy.store(false, Ordering::Release);
                    fail_pending(&reader_sidecar, "backend response stream failed");
                    break;
                }
            };
            if count == 0 {
                append_diagnostic("backend response stream closed");
                reader_sidecar.healthy.store(false, Ordering::Release);
                fail_pending(&reader_sidecar, "backend closed its response stream");
                break;
            }
            if count as u64 > MAX_JSONL_LINE_BYTES || !bytes.ends_with(b"\n") {
                append_diagnostic("backend response exceeded JSONL frame limit");
                reader_sidecar.healthy.store(false, Ordering::Release);
                fail_pending(
                    &reader_sidecar,
                    "backend response exceeded JSONL frame limit",
                );
                break;
            }
            let response: Value = match serde_json::from_slice(&bytes) {
                Ok(value) => value,
                Err(_) => {
                    append_diagnostic("backend response invalid JSON");
                    reader_sidecar.healthy.store(false, Ordering::Release);
                    fail_pending(&reader_sidecar, "backend response invalid");
                    break;
                }
            };
            if let Some(event) = response.get("event").cloned() {
                let request_id = match event.get("request_id").and_then(Value::as_str) {
                    Some(value) => value.to_owned(),
                    None => {
                        append_diagnostic("backend event missing request_id");
                        continue;
                    }
                };
                if let Ok(pending) = reader_sidecar.pending.lock() {
                    if let Some(sender) = pending.get(&request_id) {
                        let _ = sender.send(SidecarFrame::Event(event));
                    } else {
                        append_diagnostic("backend orphan event");
                    }
                }
                continue;
            }
            let request_id = match response.get("request_id").and_then(Value::as_str) {
                Some(value) => value.to_owned(),
                None => {
                    append_diagnostic("backend response missing request_id");
                    reader_sidecar.healthy.store(false, Ordering::Release);
                    fail_pending(&reader_sidecar, "backend response missing request_id");
                    break;
                }
            };
            if let Ok(mut pending) = reader_sidecar.pending.lock() {
                if let Some(sender) = pending.remove(&request_id) {
                    let _ = sender.send(SidecarFrame::Response(Ok(response)));
                } else {
                    append_diagnostic("backend orphan or duplicate response");
                }
            }
        }
    });
    Ok(sidecar)
}

fn timeout_for(action: &str) -> Duration {
    match action {
        // PyInstaller scientific runtimes can take longer on the very first Windows launch.
        // This remains a bounded startup deadline; established light RPCs stay at 10 seconds.
        "health_check" => Duration::from_secs(30),
        "inspect_dataset" | "load_dataset" | "resume_session" => Duration::from_secs(90),
        "chart_data" | "read_report" => Duration::from_secs(20),
        _ => Duration::from_secs(10),
    }
}

fn acquire_sidecar(bridge: &Bridge) -> Result<Arc<Sidecar>, String> {
    let mut slot = bridge.0.lock().map_err(|_| "backend manager unavailable")?;
    let reusable = slot
        .as_ref()
        .filter(|sidecar| {
            sidecar.healthy.load(Ordering::Acquire)
                && sidecar
                    .child
                    .lock()
                    .ok()
                    .and_then(|mut child| child.try_wait().ok())
                    .flatten()
                    .is_none()
        })
        .cloned();
    if let Some(sidecar) = reusable {
        return Ok(sidecar);
    }
    if let Some(old) = slot.take() {
        old.terminate();
    }
    let sidecar = spawn()?;
    *slot = Some(Arc::clone(&sidecar));
    Ok(sidecar)
}

fn restart_backend(bridge: &Bridge) -> Result<Value, String> {
    append_diagnostic("backend restart requested");
    let old = bridge
        .0
        .lock()
        .map_err(|_| "backend manager unavailable")?
        .take();
    if let Some(sidecar) = old {
        sidecar.healthy.store(false, Ordering::Release);
        sidecar.terminate();
    }
    Ok(json!({"status":"RESTARTED"}))
}
fn restart_sidecar(bridge: &Bridge, failed: &Arc<Sidecar>) {
    failed.healthy.store(false, Ordering::Release);
    if let Ok(mut slot) = bridge.0.lock() {
        if slot
            .as_ref()
            .is_some_and(|current| Arc::ptr_eq(current, failed))
        {
            if let Some(old) = slot.take() {
                old.terminate();
            }
        }
    }
}

fn call(bridge: &Bridge, value: Value) -> Result<Value, String> {
    call_with_progress(bridge, value, |_| {})
}

fn call_with_progress<F>(
    bridge: &Bridge,
    mut value: Value,
    mut on_event: F,
) -> Result<Value, String>
where
    F: FnMut(Value),
{
    let action = value
        .get("action")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .to_owned();
    let request_id = value
        .get("request_id")
        .and_then(Value::as_str)
        .map(str::to_owned)
        .unwrap_or_else(next_request_id);
    if let Some(request) = value.as_object_mut() {
        request.insert("request_id".into(), Value::String(request_id.clone()));
    } else {
        return Err("request invalid".into());
    }
    let sidecar = acquire_sidecar(bridge)?;
    let (sender, receiver) = mpsc::channel::<SidecarFrame>();
    sidecar
        .pending
        .lock()
        .map_err(|_| "backend pending queue unavailable")?
        .insert(request_id.clone(), sender);
    let text = serde_json::to_string(&value).map_err(|_| "request invalid")?;
    let write_result = (|| -> Result<(), std::io::Error> {
        let mut stdin = sidecar
            .stdin
            .lock()
            .map_err(|_| std::io::Error::other("backend writer unavailable"))?;
        stdin.write_all(text.as_bytes())?;
        stdin.write_all(b"\n")?;
        stdin.flush()
    })();
    if write_result.is_err() {
        if let Ok(mut pending) = sidecar.pending.lock() {
            pending.remove(&request_id);
        }
        restart_sidecar(bridge, &sidecar);
        return Err("backend communication failed".into());
    }
    let deadline = Instant::now() + timeout_for(&action);
    let response = loop {
        let remaining = deadline.saturating_duration_since(Instant::now());
        match receiver.recv_timeout(remaining) {
            Ok(SidecarFrame::Event(event)) => on_event(event),
            Ok(SidecarFrame::Response(Ok(value))) => break value,
            Ok(SidecarFrame::Response(Err(message))) => {
                restart_sidecar(bridge, &sidecar);
                return Err(message);
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                if let Ok(mut pending) = sidecar.pending.lock() {
                    pending.remove(&request_id);
                }
                restart_sidecar(bridge, &sidecar);
                append_diagnostic(&format!("backend request timed out: {}", action));
                return Err(format!("backend request timed out: {}", action));
            }
            Err(_) => {
                restart_sidecar(bridge, &sidecar);
                return Err("backend response channel failed".into());
            }
        }
    };
    if response.get("request_id").and_then(Value::as_str) != Some(request_id.as_str()) {
        restart_sidecar(bridge, &sidecar);
        return Err("backend response request_id mismatch".into());
    }
    match response.get("ok").and_then(Value::as_bool) {
        Some(true) => response
            .get("data")
            .cloned()
            .ok_or("backend response missing data".into()),
        Some(false) => Err(response_error(&response)),
        None => {
            restart_sidecar(bridge, &sidecar);
            Err("backend response missing ok flag".into())
        }
    }
}
fn metadata_path<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> {
    let dir = app
        .path()
        .app_data_dir()
        .map_err(|_| "app data unavailable")?;
    fs::create_dir_all(&dir).map_err(|_| "app data unavailable")?;
    Ok(dir.join("provider-profiles.json"))
}
fn load<R: Runtime>(app: &AppHandle<R>) -> Result<Store, String> {
    let path = metadata_path(app)?;
    if !path.exists() {
        return Ok(Store::default());
    }
    serde_json::from_slice(&fs::read(path).map_err(|_| "profile read failed")?)
        .map_err(|_| "profile parse failed".into())
}
fn save<R: Runtime>(app: &AppHandle<R>, store: &Store) -> Result<(), String> {
    fs::write(
        metadata_path(app)?,
        serde_json::to_vec_pretty(store).map_err(|_| "profile serialize failed")?,
    )
    .map_err(|_| "profile save failed".into())
}
fn entry(provider: &str) -> Result<Entry, String> {
    Entry::new(SERVICE, provider).map_err(|_| "credential store unavailable".into())
}
fn secret(provider: &str) -> Result<String, String> {
    entry(provider)?
        .get_password()
        .map_err(|_| "credential missing".into())
}
fn present(provider: &str) -> bool {
    secret(provider)
        .map(|value| !value.is_empty())
        .unwrap_or(false)
}
fn mask(provider: &str) -> Option<String> {
    let value = secret(provider).ok()?;
    Some(format!(
        "\u{2022}\u{2022}\u{2022}\u{2022}{}",
        value
            .chars()
            .rev()
            .take(4)
            .collect::<Vec<_>>()
            .into_iter()
            .rev()
            .collect::<String>()
    ))
}

fn status<R: Runtime>(app: &AppHandle<R>) -> Result<Value, String> {
    let store = load(app)?;
    Ok(
        json!({"providers":catalog(),"profiles":store.profiles.iter().map(|profile| json!({"provider":profile.provider,"label":profile.label,"model_id":profile.model_id,"base_url":profile.base_url,"configured":present(&profile.provider),"masked_key":mask(&profile.provider),"tool_calling_verified":profile.tool_calling_verified,"last_connection_test":profile.last_connection_test,"is_default":store.default_provider.as_deref()==Some(&profile.provider)})).collect::<Vec<_>>(),"default_provider":store.default_provider}),
    )
}
fn save_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> {
    let provider = value
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let display = label(provider).ok_or("unsupported provider")?;
    let model = value
        .get("model_id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim();
    let base = value
        .get("base_url")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|v| !v.is_empty())
        .map(str::to_owned);
    let api = value
        .get("api_key")
        .and_then(Value::as_str)
        .unwrap_or_default();
    if model.is_empty() {
        return Err("model id required".into());
    }
    if provider == "custom_openai_compatible" && base.is_none() {
        return Err(
            "Custom OpenAI-Compatible \u{5fc5}\u{987b}\u{586b}\u{5199} API Base URL\u{3002}".into(),
        );
    }
    if !api.is_empty() {
        entry(provider)?
            .set_password(api)
            .map_err(|_| "credential save failed")?;
    } else if !present(provider) {
        return Err("api key required".into());
    }
    let mut store = load(app)?;
    let profile = Profile {
        provider: provider.into(),
        label: display.into(),
        model_id: model.into(),
        base_url: base,
        tool_calling_verified: false,
        last_connection_test: None,
    };
    if let Some(found) = store
        .profiles
        .iter_mut()
        .find(|item| item.provider == provider)
    {
        *found = profile;
    } else {
        store.profiles.push(profile);
    }
    if value
        .get("set_default")
        .and_then(Value::as_bool)
        .unwrap_or(true)
        || store.default_provider.is_none()
    {
        store.default_provider = Some(provider.into());
    }
    save(app, &store)?;
    Ok(json!({"status":"SAVED","provider":provider,"configured":true,"masked_key":mask(provider)}))
}
fn delete_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> {
    let provider = value
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or_default();
    label(provider).ok_or("unsupported provider")?;
    if let Ok(found) = entry(provider) {
        let _ = found.delete_credential();
    }
    let mut store = load(app)?;
    store.profiles.retain(|item| item.provider != provider);
    if store.default_provider.as_deref() == Some(provider) {
        store.default_provider = store.profiles.first().map(|item| item.provider.clone());
    }
    save(app, &store)?;
    Ok(json!({"status":"DELETED","provider":provider}))
}
fn default_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> {
    let provider = value
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let mut store = load(app)?;
    if !store.profiles.iter().any(|item| item.provider == provider) || !present(provider) {
        return Err("provider unavailable".into());
    }
    store.default_provider = Some(provider.into());
    save(app, &store)?;
    Ok(json!({"status":"DEFAULT_UPDATED","provider":provider}))
}
fn probe<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> {
    let provider = value
        .get("provider")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let env_name = key_env(provider).ok_or("unsupported provider")?;
    let mut store = load(app)?;
    let profile = store
        .profiles
        .iter_mut()
        .find(|item| item.provider == provider)
        .ok_or("profile missing")?;
    let runtime = runtime_dir();
    let mut command = Command::new(node_executable());
    command
        .arg(runtime.join("agent/src/pi-connection-probe.mjs"))
        .current_dir(&runtime)
        .env("ECOMIC_BACKEND", runtime.join("ecomic-backend.exe"))
        .env("ECOMIC_PROVIDER", provider)
        .env("ECOMIC_MODEL", &profile.model_id)
        .env(env_name, secret(provider)?)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    if let Some(base) = profile.base_url.as_ref() {
        command.env("ECOMIC_BASE_URL", base);
    }
    let mut child = command.spawn().map_err(|_| "probe runtime unavailable")?;
    if let Some(stderr) = child.stderr.take() {
        drain_stderr("provider-probe", stderr);
    }
    let deadline = Instant::now() + Duration::from_secs(15);
    loop {
        if child.try_wait().map_err(|_| "probe wait failed")?.is_some() {
            break;
        }
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            profile.tool_calling_verified = false;
            profile.last_connection_test = Some("timeout".into());
            save(app, &store)?;
            return Ok(
                json!({"status":"ERROR","kind":"timeout","tool_calling_verified":false,"message":"连接超时，请检查网络、代理、模型名称或 API Base URL。"}),
            );
        }
        thread::sleep(Duration::from_millis(50));
    }
    let mut stdout = Vec::new();
    child
        .stdout
        .take()
        .ok_or("probe output unavailable")?
        .read_to_end(&mut stdout)
        .map_err(|_| "probe output unavailable")?;
    let result: Value = serde_json::from_slice(&stdout).map_err(|_| "probe response invalid")?;
    profile.tool_calling_verified = result
        .get("tool_calling_verified")
        .and_then(Value::as_bool)
        .unwrap_or(false);
    profile.last_connection_test = Some("verified".into());
    save(app, &store)?;
    Ok(result)
}

fn terminate_process_tree(child: &mut Child) {
    #[cfg(target_os = "windows")]
    {
        let _ = Command::new("taskkill")
            .args(["/PID", &child.id().to_string(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .status();
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = child.kill();
    }
    let _ = child.wait();
}

fn emit_task_event<R: Runtime>(
    app: &AppHandle<R>,
    task_id: &str,
    session_id: &str,
    mut event: Value,
) {
    append_diagnostic(&format!(
        "scientist event task={} type={}",
        task_id,
        event
            .get("type")
            .and_then(Value::as_str)
            .unwrap_or("unknown")
    ));
    if let Some(object) = event.as_object_mut() {
        object
            .entry("task_id")
            .or_insert_with(|| Value::String(task_id.into()));
        object
            .entry("session_id")
            .or_insert_with(|| Value::String(session_id.into()));
    }
    let _ = app.emit("scientist-event", event);
}

fn run_scientist_task<R: Runtime>(
    app: AppHandle<R>,
    task_id: String,
    task: Arc<ScientistTask>,
    mut command: Command,
) {
    let session_id = task.session_id.clone();
    let mut child = match command.spawn() {
        Ok(child) => child,
        Err(_) => {
            set_task_status(&task, "FAILED");
            emit_task_event(
                &app,
                &task_id,
                &session_id,
                json!({"type":"agent_error","message":"Scientist runtime could not start."}),
            );
            return;
        }
    };
    let stdout = match child.stdout.take() {
        Some(stdout) => stdout,
        None => {
            terminate_process_tree(&mut child);
            set_task_status(&task, "FAILED");
            emit_task_event(
                &app,
                &task_id,
                &session_id,
                json!({"type":"agent_error","message":"Scientist output stream unavailable."}),
            );
            return;
        }
    };
    if let Some(stderr) = child.stderr.take() {
        drain_stderr("scientist", stderr);
    }
    if let Ok(mut slot) = task.child.lock() {
        *slot = Some(child);
    }
    let (line_tx, line_rx) = mpsc::channel::<Result<String, String>>();
    thread::spawn(move || {
        for line in BufReader::new(stdout).lines() {
            if line_tx
                .send(line.map_err(|_| "Scientist output stream failed.".into()))
                .is_err()
            {
                break;
            }
        }
    });
    let deadline = Instant::now() + Duration::from_secs(30 * 60);
    let mut agent_error = false;
    loop {
        match line_rx.recv_timeout(Duration::from_millis(200)) {
            Ok(Ok(line)) => match serde_json::from_str::<Value>(&line) {
                Ok(event) => {
                    if event.get("type").and_then(Value::as_str) == Some("agent_error") {
                        agent_error = true;
                    }
                    emit_task_event(&app, &task_id, &session_id, event);
                }
                Err(_) => emit_task_event(
                    &app,
                    &task_id,
                    &session_id,
                    json!({"type":"agent_error","message":"Scientist emitted malformed JSON."}),
                ),
            },
            Ok(Err(message)) => {
                agent_error = true;
                emit_task_event(
                    &app,
                    &task_id,
                    &session_id,
                    json!({"type":"agent_error","message":message}),
                );
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) => {}
        }
        let stopped = task.child.lock().ok().and_then(|mut slot| {
            slot.as_mut()
                .and_then(|child| child.try_wait().ok())
                .flatten()
        });
        if let Some(status) = stopped {
            let state = task_status(&task);
            if state == "CANCELLED" {
                emit_task_event(
                    &app,
                    &task_id,
                    &session_id,
                    json!({"type":"agent_cancelled","message":"Scientist task was cancelled; the Session was preserved."}),
                );
            } else if status.success() && !agent_error {
                set_task_status(&task, "COMPLETED");
                emit_task_event(
                    &app,
                    &task_id,
                    &session_id,
                    json!({"type":"task_completed"}),
                );
            } else {
                set_task_status(&task, "FAILED");
                emit_task_event(
                    &app,
                    &task_id,
                    &session_id,
                    json!({"type":"task_failed","message":"Scientist task failed; the Session was preserved."}),
                );
            }
            break;
        }
        if Instant::now() >= deadline {
            set_task_status(&task, "TIMED_OUT");
            if let Ok(mut slot) = task.child.lock() {
                if let Some(child) = slot.as_mut() {
                    terminate_process_tree(child);
                }
            }
            emit_task_event(
                &app,
                &task_id,
                &session_id,
                json!({"type":"task_failed","code":"TASK_TIMEOUT","message":"Scientist task timed out and was safely terminated; the Session was preserved."}),
            );
            break;
        }
    }
    if let Ok(mut slot) = task.child.lock() {
        *slot = None;
    }
}

fn scientist_start<R: Runtime>(
    app: &AppHandle<R>,
    bridge: &Bridge,
    tasks: &TaskManager,
    value: &Value,
) -> Result<Value, String> {
    let session_id = value
        .get("session_id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_owned();
    let question = value
        .get("question")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim()
        .to_owned();
    if session_id.is_empty() || question.is_empty() {
        return Err("session and question required".into());
    }
    if tasks.0.lock().map_err(|_| "task manager unavailable")?.values().any(|task| task.session_id == session_id && matches!(task_status(task), status if status == "STARTING" || status == "RUNNING" || status == "CANCELLING")) { return Err("a Scientist task is already active for this Session".into()); }
    let _ = call(
        bridge,
        json!({"action":"set_research_question","payload":{"session_id":session_id,"question":question}}),
    )?;
    let store = load(app)?;
    let provider = store
        .default_provider
        .as_deref()
        .ok_or("default provider missing")?;
    let profile = store
        .profiles
        .iter()
        .find(|item| item.provider == provider)
        .ok_or("profile missing")?;
    if !profile.tool_calling_verified {
        return Err("tool calling verification required".into());
    }
    let runtime = runtime_dir();
    let mut command = Command::new(node_executable());
    let runner = env::var_os("ECOMIC_SCIENTIST_RUNNER")
        .map(PathBuf::from)
        .unwrap_or_else(|| runtime.join("agent/src/desktop-scientist-runner-v2.mjs"));
    command
        .arg(runner)
        .current_dir(&runtime)
        .env("ECOMIC_BACKEND", runtime.join("ecomic-backend.exe"))
        .env("ECOMIC_PROVIDER", provider)
        .env("ECOMIC_MODEL", &profile.model_id)
        .env(
            key_env(provider).ok_or("unsupported provider")?,
            secret(provider)?,
        )
        .env("ECOMIC_SESSION_ID", &session_id)
        .env("ECOMIC_RESEARCH_QUESTION", &question)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    #[cfg(target_os = "windows")]
    command.creation_flags(CREATE_NO_WINDOW);
    if let Some(base) = profile.base_url.as_ref() {
        command.env("ECOMIC_BASE_URL", base);
    }
    let id = task_id();
    let task = Arc::new(ScientistTask {
        session_id: session_id.clone(),
        status: Mutex::new("STARTING".into()),
        child: Mutex::new(None),
    });
    tasks
        .0
        .lock()
        .map_err(|_| "task manager unavailable")?
        .insert(id.clone(), Arc::clone(&task));
    let app_handle = app.clone();
    let task_id_for_thread = id.clone();
    let task_session_id = session_id.clone();
    thread::spawn(move || {
        set_task_status(&task, "RUNNING");
        emit_task_event(
            &app_handle,
            &task_id_for_thread,
            &task_session_id,
            json!({"type":"agent_started"}),
        );
        run_scientist_task(app_handle, task_id_for_thread, task, command);
    });
    Ok(json!({"task_id":id,"session_id":session_id,"status":"STARTING"}))
}

fn scientist_cancel<R: Runtime>(
    app: &AppHandle<R>,
    tasks: &TaskManager,
    value: &Value,
) -> Result<Value, String> {
    let id = value
        .get("task_id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let task = tasks
        .0
        .lock()
        .map_err(|_| "task manager unavailable")?
        .get(id)
        .cloned()
        .ok_or("Scientist task not found")?;
    let status = task_status(&task);
    if !matches!(status.as_str(), "STARTING" | "RUNNING" | "CANCELLING") {
        return Ok(json!({"task_id":id,"status":status}));
    }
    set_task_status(&task, "CANCELLING");
    emit_task_event(
        app,
        id,
        &task.session_id,
        json!({"type":"agent_cancelling"}),
    );
    if let Ok(mut slot) = task.child.lock() {
        if let Some(child) = slot.as_mut() {
            terminate_process_tree(child);
        }
    }
    set_task_status(&task, "CANCELLED");
    Ok(json!({"task_id":id,"status":"CANCELLED"}))
}

fn shutdown_desktop_tasks(bridge: &Bridge, tasks: &TaskManager) {
    append_diagnostic("desktop shutdown: terminating owned backend and Scientist task trees");
    let sidecar = bridge.0.lock().ok().and_then(|mut slot| slot.take());
    if let Some(sidecar) = sidecar {
        sidecar.healthy.store(false, Ordering::Release);
        sidecar.terminate();
    }
    let active_tasks = tasks
        .0
        .lock()
        .ok()
        .map(|items| items.values().cloned().collect::<Vec<_>>())
        .unwrap_or_default();
    for task in active_tasks {
        let status = task_status(&task);
        if matches!(status.as_str(), "STARTING" | "RUNNING" | "CANCELLING") {
            set_task_status(&task, "CANCELLED");
        }
        if let Ok(mut slot) = task.child.lock() {
            if let Some(child) = slot.as_mut() {
                terminate_process_tree(child);
            }
            *slot = None;
        }
    }
}

fn scientist_status(tasks: &TaskManager, value: &Value) -> Result<Value, String> {
    let id = value
        .get("task_id")
        .and_then(Value::as_str)
        .unwrap_or_default();
    let task = tasks
        .0
        .lock()
        .map_err(|_| "task manager unavailable")?
        .get(id)
        .cloned()
        .ok_or("Scientist task not found")?;
    Ok(json!({"task_id":id,"session_id":task.session_id,"status":task_status(&task)}))
}

fn open_report_location(bridge: &Bridge, value: &Value) -> Result<Value, String> {
    let session_id = value
        .get("session_id")
        .and_then(Value::as_str)
        .unwrap_or_default()
        .trim();
    if session_id.is_empty() {
        return Err("session id required".into());
    }
    let report = call(
        bridge,
        json!({"action":"read_report","payload":{"session_id":session_id}}),
    )?;
    let path = report
        .get("path")
        .and_then(Value::as_str)
        .ok_or("report path unavailable")?;
    #[cfg(target_os = "windows")]
    {
        Command::new("explorer.exe")
            .arg(format!("/select,{}", path))
            .spawn()
            .map_err(|_| "unable to open report location")?;
    }
    #[cfg(not(target_os = "windows"))]
    {
        let _ = path;
        return Err("report location is available on Windows only".into());
    }
    Ok(json!({"status":"OPENED","session_id":session_id}))
}
#[tauri::command]
async fn desktop_bridge<R: Runtime>(
    app: AppHandle<R>,
    bridge: tauri::State<'_, Bridge>,
    tasks: tauri::State<'_, TaskManager>,
    action: String,
    payload: Value,
) -> Result<Value, String> {
    match action.as_str() {
        "inspect_dataset" => {
            let owned_app = app.clone();
            let owned_bridge = bridge.inner().clone();
            tauri::async_runtime::spawn_blocking(move || {
                call_with_progress(
                    &owned_bridge,
                    json!({"action":"inspect_dataset","payload":payload}),
                    |event| {
                        let _ = owned_app.emit("precheck-event", event);
                    },
                )
            })
            .await
            .map_err(|_| "dataset precheck interrupted".to_string())?
        }
        "provider_status" => status(&app),
        "provider_save" => save_profile(&app, &payload),
        "provider_delete" => delete_profile(&app, &payload),
        "provider_set_default" => default_profile(&app, &payload),
        "provider_validate" => {
            let provider = payload
                .get("provider")
                .and_then(Value::as_str)
                .unwrap_or_default();
            if label(provider).is_none() {
                Err("unsupported provider".into())
            } else if !present(provider) {
                Err("credential missing".into())
            } else {
                Ok(
                    json!({"status":"READY_FOR_CONNECTION_TEST","message":"Connection test may use a small number of tokens."}),
                )
            }
        }
        "provider_test_connection" => probe(&app, &payload),
        "backend_restart" => restart_backend(&bridge),
        "scientist_start" => {
            let owned_app = app.clone();
            let owned_bridge = bridge.inner().clone();
            let owned_tasks = tasks.inner().clone();
            tauri::async_runtime::spawn_blocking(move || {
                scientist_start(&owned_app, &owned_bridge, &owned_tasks, &payload)
            })
            .await
            .map_err(|_| "scientist task start interrupted".to_string())?
        }
        "scientist_cancel" => scientist_cancel(&app, &tasks, &payload),
        "scientist_status" => scientist_status(&tasks, &payload),
        "report_open_location" => open_report_location(&bridge, &payload),
        _ => {
            let request = json!({"action":action,"payload":payload});
            let owned_bridge = bridge.inner().clone();
            tauri::async_runtime::spawn_blocking(move || call(&owned_bridge, request))
                .await
                .map_err(|_| "backend task interrupted".to_string())?
        }
    }
}

pub fn run() {
    let builder = tauri::Builder::default()
        .setup(|app| {
            let bundled = app
                .path()
                .resource_dir()
                .map(|path| path.join("ecomic-agent"))
                .unwrap_or_else(|_| root().join("release/runtime/ecomic-agent"));
            let selected = if bundled.is_dir() {
                bundled
            } else {
                root().join("release/runtime/ecomic-agent")
            };
            let _ = RUNTIME_DIR.set(selected);
            if let Ok(data) = app.path().app_data_dir() {
                let _ = DIAGNOSTIC_LOG_DIR.set(data.join("logs"));
            }
            append_diagnostic("desktop runtime started");
            Ok(())
        })
        .manage(Bridge(Arc::new(Mutex::new(None))))
        .manage(TaskManager(Arc::new(Mutex::new(HashMap::new()))))
        .plugin(tauri_plugin_dialog::init());

    #[cfg(feature = "e2e")]
    let builder = builder.plugin(tauri_plugin_wdio::init());

    let application = builder
        .invoke_handler(tauri::generate_handler![desktop_bridge])
        .build(tauri::generate_context!())
        .expect("desktop build failed");
    application.run(|app, event| {
        if matches!(
            event,
            tauri::RunEvent::Exit | tauri::RunEvent::ExitRequested { .. }
        ) {
            let bridge = app.state::<Bridge>();
            let tasks = app.state::<TaskManager>();
            shutdown_desktop_tasks(&bridge, &tasks);
        }
    });
}
#[cfg(all(test, target_os = "windows"))]
mod process_cleanup_tests {
    use super::*;

    #[test]
    fn diagnostic_redaction_removes_provider_credentials() {
        let value = redact_diagnostic(
            "Authorization: Bearer sk-live-secret OPENAI_API_KEY=abc123 DEEPSEEK_API_KEY=xyz789",
        );
        assert!(!value.contains("sk-live-secret"));
        assert!(!value.contains("abc123"));
        assert!(!value.contains("xyz789"));
        assert!(value.contains("[REDACTED]"));
    }

    #[test]
    fn desktop_shutdown_cancels_owned_scientist_process_tree() {
        let mut command = Command::new("cmd");
        command
            .args(["/C", "ping -t 127.0.0.1 > NUL"])
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .creation_flags(CREATE_NO_WINDOW);
        let child = command.spawn().expect("test child must start");
        let child_pid = child.id();
        let task = Arc::new(ScientistTask {
            session_id: "session_test".into(),
            status: Mutex::new("RUNNING".into()),
            child: Mutex::new(Some(child)),
        });
        let tasks = TaskManager(Arc::new(Mutex::new(HashMap::from([(
            "task_test".into(),
            Arc::clone(&task),
        )]))));
        let bridge = Bridge(Arc::new(Mutex::new(None)));

        shutdown_desktop_tasks(&bridge, &tasks);

        assert_eq!(task_status(&task), "CANCELLED");
        assert!(task.child.lock().expect("child lock").is_none());
        thread::sleep(Duration::from_millis(250));
        let listing = Command::new("tasklist")
            .args(["/FI", &format!("PID eq {}", child_pid), "/FO", "CSV", "/NH"])
            .creation_flags(CREATE_NO_WINDOW)
            .output()
            .expect("tasklist must run");
        assert!(
            !String::from_utf8_lossy(&listing.stdout).contains(&child_pid.to_string()),
            "owned Scientist parent process must not survive desktop shutdown"
        );
    }
}
