use keyring::Entry;
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::{env, fs, io::{BufRead, BufReader, Read, Write}, path::PathBuf, process::{Child, ChildStdin, ChildStdout, Command, Stdio}, sync::{Mutex, OnceLock}, thread, time::{Duration, Instant}};
use tauri::{AppHandle, Emitter, Manager, Runtime};

const SERVICE: &str = "ECOMIC Desktop";
static RUNTIME_DIR: OnceLock<PathBuf> = OnceLock::new();
const CREATE_NO_WINDOW: u32 = 0x08000000;
#[cfg(target_os = "windows")]
use std::os::windows::process::CommandExt;
struct Sidecar { child: Child, stdin: ChildStdin, stdout: BufReader<ChildStdout> }
struct Bridge(Mutex<Option<Sidecar>>);
impl Drop for Sidecar {
 fn drop(&mut self) {
  let _ = self.stdin.flush();
  if self.child.try_wait().ok().flatten().is_none() {
   let _ = self.child.kill();
   let _ = self.child.wait();
  }
 }
}
#[derive(Clone, Deserialize, Serialize)]
struct Profile { provider: String, label: String, model_id: String, base_url: Option<String>, tool_calling_verified: bool, last_connection_test: Option<String> }
#[derive(Default, Deserialize, Serialize)]
struct Store { default_provider: Option<String>, profiles: Vec<Profile> }

fn root() -> PathBuf { PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().and_then(|p| p.parent()).expect("desktop layout").to_path_buf() }
fn label(p: &str) -> Option<&'static str> { match p { "openai" => Some("OpenAI"), "anthropic" => Some("Anthropic"), "deepseek" => Some("DeepSeek"), "google" => Some("Google Gemini"), "openrouter" => Some("OpenRouter"), "moonshot" => Some("Moonshot"), "qwen" => Some("Qwen"), "minimax" => Some("MiniMax"), "custom_openai_compatible" => Some("Custom OpenAI-Compatible"), _ => None } }
fn key_env(p: &str) -> Option<&'static str> { match p { "openai" => Some("OPENAI_API_KEY"), "anthropic" => Some("ANTHROPIC_API_KEY"), "deepseek" => Some("DEEPSEEK_API_KEY"), "google" => Some("GEMINI_API_KEY"), "openrouter" => Some("OPENROUTER_API_KEY"), "moonshot" => Some("MOONSHOT_API_KEY"), "qwen" => Some("QWEN_TOKEN_PLAN_CN_API_KEY"), "minimax" => Some("MINIMAX_API_KEY"), "custom_openai_compatible" => Some("ECOMIC_CUSTOM_API_KEY"), _ => None } }
fn catalog() -> Vec<Value> { [("openai","OpenAI",false),("anthropic","Anthropic",false),("deepseek","DeepSeek",false),("google","Google Gemini",false),("openrouter","OpenRouter",false),("moonshot","Moonshot",false),("qwen","Qwen",false),("minimax","MiniMax",false),("custom_openai_compatible","Custom OpenAI-Compatible",true)].into_iter().map(|(id,label,requires_base_url)| json!({"id":id,"label":label,"requires_base_url":requires_base_url})).collect() }

fn runtime_dir() -> PathBuf { RUNTIME_DIR.get().cloned().unwrap_or_else(|| root().join("release/runtime/ecomic-agent")) }
fn backend_executable() -> PathBuf { env::var_os("ECOMIC_BACKEND").map(PathBuf::from).unwrap_or_else(|| runtime_dir().join("ecomic-backend.exe")) }
fn node_executable() -> PathBuf { env::var_os("ECOMIC_NODE").map(PathBuf::from).unwrap_or_else(|| runtime_dir().join("node.exe")) }
fn spawn() -> Result<Sidecar, String> { let backend = backend_executable(); if !backend.is_file() { return Err("bundled backend executable is unavailable".into()); } let mut command = Command::new(backend); command.current_dir(runtime_dir()).stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null()); #[cfg(target_os = "windows")] command.creation_flags(CREATE_NO_WINDOW); let mut child = command.spawn().map_err(|_| "backend start failed")?; Ok(Sidecar { stdin: child.stdin.take().ok_or("backend stdin unavailable")?, stdout: BufReader::new(child.stdout.take().ok_or("backend stdout unavailable")?), child }) }
fn call(bridge: &Bridge, value: Value) -> Result<Value, String> { let mut lock = bridge.0.lock().map_err(|_| "backend lock unavailable")?; if lock.as_mut().map(|sidecar| sidecar.child.try_wait().ok().flatten().is_some()).unwrap_or(true) { *lock = Some(spawn()?); } let sidecar = lock.as_mut().expect("sidecar initialized"); let text = serde_json::to_string(&value).map_err(|_| "request invalid")?; sidecar.stdin.write_all(text.as_bytes()).and_then(|_| sidecar.stdin.write_all(b"\n")).and_then(|_| sidecar.stdin.flush()).map_err(|_| "backend communication failed")?; let mut line = String::new(); sidecar.stdout.read_line(&mut line).map_err(|_| "backend response failed")?; serde_json::from_str(&line).map_err(|_| "backend response invalid".into()) }

fn metadata_path<R: Runtime>(app: &AppHandle<R>) -> Result<PathBuf, String> { let dir = app.path().app_data_dir().map_err(|_| "app data unavailable")?; fs::create_dir_all(&dir).map_err(|_| "app data unavailable")?; Ok(dir.join("provider-profiles.json")) }
fn load<R: Runtime>(app: &AppHandle<R>) -> Result<Store, String> { let path = metadata_path(app)?; if !path.exists() { return Ok(Store::default()); } serde_json::from_slice(&fs::read(path).map_err(|_| "profile read failed")?).map_err(|_| "profile parse failed".into()) }
fn save<R: Runtime>(app: &AppHandle<R>, store: &Store) -> Result<(), String> { fs::write(metadata_path(app)?, serde_json::to_vec_pretty(store).map_err(|_| "profile serialize failed")?).map_err(|_| "profile save failed".into()) }
fn entry(provider: &str) -> Result<Entry, String> { Entry::new(SERVICE, provider).map_err(|_| "credential store unavailable".into()) }
fn secret(provider: &str) -> Result<String, String> { entry(provider)?.get_password().map_err(|_| "credential missing".into()) }
fn present(provider: &str) -> bool { secret(provider).map(|value| !value.is_empty()).unwrap_or(false) }
fn mask(provider: &str) -> Option<String> { let value = secret(provider).ok()?; Some(format!("\u{2022}\u{2022}\u{2022}\u{2022}{}", value.chars().rev().take(4).collect::<Vec<_>>().into_iter().rev().collect::<String>())) }

fn status<R: Runtime>(app: &AppHandle<R>) -> Result<Value, String> { let store = load(app)?; Ok(json!({"providers":catalog(),"profiles":store.profiles.iter().map(|profile| json!({"provider":profile.provider,"label":profile.label,"model_id":profile.model_id,"base_url":profile.base_url,"configured":present(&profile.provider),"masked_key":mask(&profile.provider),"tool_calling_verified":profile.tool_calling_verified,"last_connection_test":profile.last_connection_test,"is_default":store.default_provider.as_deref()==Some(&profile.provider)})).collect::<Vec<_>>(),"default_provider":store.default_provider})) }
fn save_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> { let provider = value.get("provider").and_then(Value::as_str).unwrap_or_default(); let display = label(provider).ok_or("unsupported provider")?; let model = value.get("model_id").and_then(Value::as_str).unwrap_or_default().trim(); let base = value.get("base_url").and_then(Value::as_str).map(str::trim).filter(|v| !v.is_empty()).map(str::to_owned); let api = value.get("api_key").and_then(Value::as_str).unwrap_or_default(); if model.is_empty() { return Err("model id required".into()); } if provider == "custom_openai_compatible" && base.is_none() { return Err("Custom OpenAI-Compatible \u{5fc5}\u{987b}\u{586b}\u{5199} API Base URL\u{3002}".into()); } if !api.is_empty() { entry(provider)?.set_password(api).map_err(|_| "credential save failed")?; } else if !present(provider) { return Err("api key required".into()); } let mut store = load(app)?; let profile = Profile { provider: provider.into(), label: display.into(), model_id: model.into(), base_url: base, tool_calling_verified: false, last_connection_test: None }; if let Some(found) = store.profiles.iter_mut().find(|item| item.provider == provider) { *found = profile; } else { store.profiles.push(profile); } if value.get("set_default").and_then(Value::as_bool).unwrap_or(true) || store.default_provider.is_none() { store.default_provider = Some(provider.into()); } save(app, &store)?; Ok(json!({"status":"SAVED","provider":provider,"configured":true,"masked_key":mask(provider)})) }
fn delete_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> { let provider = value.get("provider").and_then(Value::as_str).unwrap_or_default(); label(provider).ok_or("unsupported provider")?; if let Ok(found) = entry(provider) { let _ = found.delete_credential(); } let mut store = load(app)?; store.profiles.retain(|item| item.provider != provider); if store.default_provider.as_deref() == Some(provider) { store.default_provider = store.profiles.first().map(|item| item.provider.clone()); } save(app, &store)?; Ok(json!({"status":"DELETED","provider":provider})) }
fn default_profile<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> { let provider = value.get("provider").and_then(Value::as_str).unwrap_or_default(); let mut store = load(app)?; if !store.profiles.iter().any(|item| item.provider == provider) || !present(provider) { return Err("provider unavailable".into()); } store.default_provider = Some(provider.into()); save(app, &store)?; Ok(json!({"status":"DEFAULT_UPDATED","provider":provider})) }
fn probe<R: Runtime>(app: &AppHandle<R>, value: &Value) -> Result<Value, String> {
 let provider = value.get("provider").and_then(Value::as_str).unwrap_or_default();
 let env_name = key_env(provider).ok_or("unsupported provider")?;
 let mut store = load(app)?;
 let profile = store.profiles.iter_mut().find(|item| item.provider == provider).ok_or("profile missing")?;
 let runtime = runtime_dir();
 let mut command = Command::new(node_executable());
 command.arg(runtime.join("agent/src/pi-connection-probe.mjs")).current_dir(&runtime).env("ECOMIC_BACKEND", runtime.join("ecomic-backend.exe")).env("ECOMIC_PROVIDER", provider).env("ECOMIC_MODEL", &profile.model_id).env(env_name, secret(provider)?).stdout(Stdio::piped()).stderr(Stdio::null());
 #[cfg(target_os = "windows")] command.creation_flags(CREATE_NO_WINDOW);
 if let Some(base) = profile.base_url.as_ref() { command.env("ECOMIC_BASE_URL", base); }
 let mut child = command.spawn().map_err(|_| "probe runtime unavailable")?;
 let deadline = Instant::now() + Duration::from_secs(15);
 loop {
  if child.try_wait().map_err(|_| "probe wait failed")?.is_some() { break; }
  if Instant::now() >= deadline {
   let _ = child.kill();
   let _ = child.wait();
   profile.tool_calling_verified = false;
   profile.last_connection_test = Some("timeout".into());
   save(app, &store)?;
   return Ok(json!({"status":"ERROR","kind":"timeout","tool_calling_verified":false,"message":"连接超时，请检查网络、代理、模型名称或 API Base URL。"}));
  }
  thread::sleep(Duration::from_millis(50));
 }
 let mut stdout = Vec::new();
 child.stdout.take().ok_or("probe output unavailable")?.read_to_end(&mut stdout).map_err(|_| "probe output unavailable")?;
 let result: Value = serde_json::from_slice(&stdout).map_err(|_| "probe response invalid")?;
 profile.tool_calling_verified = result.get("tool_calling_verified").and_then(Value::as_bool).unwrap_or(false);
 profile.last_connection_test = Some("verified".into());
 save(app, &store)?;
 Ok(result)
}

fn scientist<R: Runtime>(app: &AppHandle<R>, bridge: &Bridge, value: &Value) -> Result<Value, String> {
 let session_id = value.get("session_id").and_then(Value::as_str).unwrap_or_default().trim(); let question = value.get("question").and_then(Value::as_str).unwrap_or_default().trim();
 if session_id.is_empty() || question.is_empty() { return Err("session and question required".into()); }
 let _ = call(&bridge, json!({"action":"set_research_question","payload":{"session_id":session_id,"question":question}}))?;
 let store = load(app)?; let provider = store.default_provider.as_deref().ok_or("default provider missing")?; let profile = store.profiles.iter().find(|item| item.provider == provider).ok_or("profile missing")?;
 if !profile.tool_calling_verified { return Err("tool calling verification required".into()); }
 let runtime = runtime_dir(); let mut command = Command::new(node_executable());
 command.arg(runtime.join("agent/src/desktop-scientist-runner-v2.mjs")).current_dir(&runtime).env("ECOMIC_BACKEND", runtime.join("ecomic-backend.exe")).env("ECOMIC_PROVIDER", provider).env("ECOMIC_MODEL", &profile.model_id).env(key_env(provider).ok_or("unsupported provider")?, secret(provider)?).env("ECOMIC_SESSION_ID", session_id).env("ECOMIC_RESEARCH_QUESTION", question).stdout(Stdio::piped()).stderr(Stdio::null());
 #[cfg(target_os = "windows")] command.creation_flags(CREATE_NO_WINDOW);
 if let Some(base) = profile.base_url.as_ref() { command.env("ECOMIC_BASE_URL", base); }
 let mut child = command.spawn().map_err(|_| "agent runtime unavailable")?; let stdout = child.stdout.take().ok_or("agent output unavailable")?; let mut events = Vec::<Value>::new();
 for line in BufReader::new(stdout).lines() { let line = line.map_err(|_| "agent output unavailable")?; if let Ok(mut event) = serde_json::from_str::<Value>(&line) { if event.get("session_id").is_none() { if let Some(object) = event.as_object_mut() { object.insert("session_id".into(), Value::String(session_id.into())); } } let _ = app.emit("scientist-event", &event); events.push(event); } }
 let status = child.wait().map_err(|_| "agent wait failed")?; if !status.success() || events.iter().any(|event| event.get("type").and_then(Value::as_str) == Some("agent_error")) { return Err("scientist agent failed".into()); }
 Ok(json!({"status":"COMPLETED","session_id":session_id,"events":events}))
}

fn open_report_location(bridge: &Bridge, value: &Value) -> Result<Value, String> {
 let session_id = value.get("session_id").and_then(Value::as_str).unwrap_or_default().trim();
 if session_id.is_empty() { return Err("session id required".into()); }
 let report = call(bridge, json!({"action":"read_report","payload":{"session_id":session_id}}))?;
 let path = report.get("path").and_then(Value::as_str).ok_or("report path unavailable")?;
 #[cfg(target_os = "windows")]
 { Command::new("explorer.exe").arg(format!("/select,{}", path)).spawn().map_err(|_| "unable to open report location")?; }
 #[cfg(not(target_os = "windows"))]
 { let _ = path; return Err("report location is available on Windows only".into()); }
 Ok(json!({"status":"OPENED","session_id":session_id}))
}
#[tauri::command]
fn desktop_bridge<R: Runtime>(app: AppHandle<R>, bridge: tauri::State<'_, Bridge>, action: String, payload: Value) -> Result<Value, String> { match action.as_str() { "provider_status" => status(&app), "provider_save" => save_profile(&app, &payload), "provider_delete" => delete_profile(&app, &payload), "provider_set_default" => default_profile(&app, &payload), "provider_validate" => { let provider = payload.get("provider").and_then(Value::as_str).unwrap_or_default(); if label(provider).is_none() { Err("unsupported provider".into()) } else if !present(provider) { Err("credential missing".into()) } else { Ok(json!({"status":"READY_FOR_CONNECTION_TEST","message":"Connection test may use a small number of tokens."})) } }, "provider_test_connection" => probe(&app, &payload), "scientist_start" => scientist(&app, &bridge, &payload), "report_open_location" => open_report_location(&bridge, &payload), _ => call(&bridge, json!({"action":action,"payload":payload})) } }

pub fn run() { tauri::Builder::default().setup(|app| { let bundled = app.path().resource_dir().map(|path| path.join("ecomic-agent")).unwrap_or_else(|_| root().join("release/runtime/ecomic-agent")); let selected = if bundled.is_dir() { bundled } else { root().join("release/runtime/ecomic-agent") }; let _ = RUNTIME_DIR.set(selected); Ok(()) }).manage(Bridge(Mutex::new(None))).plugin(tauri_plugin_dialog::init()).plugin(tauri_plugin_wdio::init()).plugin(tauri_plugin_wdio_webdriver::init()).invoke_handler(tauri::generate_handler![desktop_bridge]).run(tauri::generate_context!()).expect("desktop run failed"); }