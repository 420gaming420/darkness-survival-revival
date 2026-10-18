# Recompile APK with debug flag
apktool b project -o project.apk
if [ $? -ne 0 ]; then
    echo "Error: Compilation failed."
    exit 1
fi

# Sign APK with debug keystore
jarsigner -sigalg SHA1withRSA -digestalg SHA1 -keystore mykeystore.jks -storepass password -keypass password project.apk debug_alias > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Error: Signing failed."
    exit 1
fi

echo "APK compiled and signed successfully."
