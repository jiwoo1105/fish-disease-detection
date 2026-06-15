import os

home = os.path.expanduser("~")  # e.g. C:\Users\<user>
sdk_dir = os.path.join(home, "AppData", "Local", "Android", "sdk")
flutter_sdk = os.path.join(home, "Documents", "flutter")


def esc(p):
    out = []
    for ch in p:
        if ch == "\\":
            out.append("\\\\")          # path separator -> escaped backslash
        elif ord(ch) < 128:
            out.append(ch)
        else:
            out.append("\\u%04x" % ord(ch))  # non-ASCII -> \uXXXX
    return "".join(out)


lines = [
    "sdk.dir=" + esc(sdk_dir),
    "flutter.sdk=" + esc(flutter_sdk),
    "flutter.buildMode=debug",
    "flutter.versionName=1.0.0",
    "flutter.versionCode=1",
]
with open("local.properties", "w", encoding="ascii") as f:
    f.write("\n".join(lines) + "\n")
print("WROTE local.properties")
