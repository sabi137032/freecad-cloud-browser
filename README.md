# FreeCAD Cloud Browser

A FreeCAD workbench plugin that lets you browse and open files directly from remote storage, without leaving FreeCAD.

## Supported Providers

| Provider | Auth Method | Notes |
|---|---|---|
| S3 | Access Key + Secret | Works with Amazon S3, MinIO, Wasabi, Backblaze B2, and any S3-compatible storage |
| FTP / FTPS / SFTP | Username + Password / SSH key | |
| WebDAV | Basic / Digest Auth | Works with Nextcloud, ownCloud, etc. |

## Installation

The recommended way is via the **FreeCAD Addon Manager** (Tools → Addon Manager). Dependencies are installed automatically.

### Manual installation

Copy the `freecad-cloud-browser` folder to your FreeCAD Mod directory:

| OS | Path |
|---|---|
| Windows | `%APPDATA%\FreeCAD\Mod\freecad-cloud-browser` |
| macOS | `~/Library/Preferences/FreeCAD/Mod/freecad-cloud-browser` |
| Linux | `~/.local/share/FreeCAD/Mod/freecad-cloud-browser` |

Then restart FreeCAD. The "Cloud Browser" workbench will appear in the workbench dropdown.

## Usage

1. Switch to the **Cloud Browser** workbench
2. Go to **Cloud Browser → Add Cloud Provider** and configure an account
3. Open the browser panel via **Cloud Browser → Open Cloud Browser**
4. Select your account, browse the remote folders, and double-click any file to open it in FreeCAD

### Supported file formats

All formats natively supported by FreeCAD are shown:
`.FCStd`, `.step`, `.stp`, `.iges`, `.igs`, `.stl`, `.obj`, `.dxf`, `.svg`, `.brep`, `.3mf`, `.ifc`, `.wrl`, and more.

## Provider Setup

### S3

Use any S3-compatible storage provider (Amazon S3, MinIO, Wasabi, Backblaze B2, etc.).

Provide:
- **Endpoint URL** — leave blank for Amazon S3, or enter the custom endpoint (e.g. `https://s3.your-region.backblazeb2.com`)
- **Bucket name**
- **Access Key ID** and **Secret Access Key**
- **Region** (required for Amazon S3, optional for others)

For Amazon S3, the IAM user needs at minimum: `s3:ListBucket`, `s3:GetObject`.

### FTP / SFTP

Enter host, port, username, and password (or SSH private key path for SFTP).

### WebDAV

Works with any WebDAV server including Nextcloud, ownCloud, and generic WebDAV endpoints. Enter the full server URL including the DAV path (e.g. `https://cloud.example.com/remote.php/dav/files/username/`).

## Architecture

```
freecad-cloud-browser/
├── InitGui.py                  # FreeCAD workbench registration
├── CloudBrowserWorkbench.py    # Commands and toolbar
├── check_deps.py               # Dependency availability checker
├── providers/
│   ├── base.py                 # Abstract CloudProvider base class
│   ├── s3.py
│   ├── ftp.py
│   └── webdav.py
├── ui/
│   ├── browser_panel.py        # Main browsing panel (FreeCAD task panel)
│   └── provider_dialog.py      # Add / manage provider dialogs
├── core/
│   ├── auth_manager.py         # Credential storage (keyring + fallback)
│   ├── config_store.py         # JSON config persistence
│   └── file_cache.py           # Local download cache
└── requirements.txt
```

## Configuration storage

- Non-sensitive settings are stored in `<FreeCAD user dir>/CloudBrowser/config.json`
- Sensitive credentials (passwords, keys) are stored in the **system keychain** via `keyring` when available, or encrypted via `cryptography` (Fernet) as a fallback

## License

MIT
