Windows icons are generated from the existing Mac asset:
`app/EXO/EXO/Assets.xcassets/AppIcon.appiconset/1024-mac.png`.

From `app/windows`, regenerate with:

```powershell
Copy-Item ../EXO/EXO/Assets.xcassets/AppIcon.appiconset/1024-mac.png ../../build/windows-runtime/mac-icon.webp
& .\node_modules\.bin\tauri.cmd icon ../../build/windows-runtime/mac-icon.webp --output src-tauri/icons
```

The About view uses a byte-for-byte copy of the Mac 512-pixel asset. Keep the
Mac originals unchanged. The Mac files have a `.png` name but contain WebP;
the temporary extension lets the converter select the correct decoder.
Windows needs ICO and PNG resources; ICNS and mobile
resources are not part of this desktop package.
