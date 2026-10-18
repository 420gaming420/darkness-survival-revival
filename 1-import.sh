# Decompile APK
if [ -z "$1" ]; then
    echo "Error: Missing APK argument. Usage: $0 <path/to/game.apk>"
    exit 1
fi

apktool d "$1" -o project

# Make it debuggable
echo Adding debug mode to AndroidManifest.xml
sed -i 's/<application /<application android:debuggable="true" /' project/AndroidManifest.xml

# Android requires all APKs to be signed before installation.
if [ ! -f "mykeystore.jks" ]; then
    keytool -genkeypair -v -keystore mykeystore.jks -alias debug_alias -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Debug, OU=Dev, O=Debug, L=City, ST=State, C=US" -storepass password -keypass password
fi
