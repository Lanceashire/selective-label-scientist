use serde::Serialize;

#[derive(Serialize)]
struct DesktopHealth { application: &'static str, shell: &'static str, status: &'static str }

#[tauri::command]
fn desktop_health() -> DesktopHealth { DesktopHealth { application: "ECOMIC Desktop", shell: "Tauri 2 + React", status: "ready" } }

pub fn run() {
  tauri::Builder::default()
    .plugin(tauri_plugin_dialog::init())
    .invoke_handler(tauri::generate_handler![desktop_health])
    .run(tauri::generate_context!())
    .expect("failed to run ECOMIC Desktop");
}
