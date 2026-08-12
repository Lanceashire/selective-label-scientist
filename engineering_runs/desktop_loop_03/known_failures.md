# Known failures resolved in this loop

1. The first `keyring` integration compiled but used the crate's default non-persistent backend because the Windows-native feature was not enabled. The release E2E correctly caught this when it received no masked value. The dependency was changed to enable `windows-native`, after which the same E2E passed against Windows Credential Manager.

2. The custom OpenAI-Compatible validation was correctly rejected by Rust but initially rendered as a generic frontend error because Tauri string rejections are not always JavaScript `Error` objects. The UI now preserves both string and `Error.message` responses, and the native E2E verifies the exact Chinese validation message.

3. Tauri bundle generation initially failed because MSI packaging did not have an explicit `.ico` entry. The existing `icons/icon.ico` is now referenced in `tauri.conf.json`; both NSIS and MSI builds pass.
