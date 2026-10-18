### Note
Most of this is just me guessing things, so some stuff may be wrong.
If you want to use these tools, you will need to extract the textdata_en.dat file from the game APK into this folder in order to use these scripts.
You can also just copy it if the APK is already extracted into project/

The file path is project/assets/textdata_en.dat

# What these tools are
These are simple python scripts I vibe coded to help me decode the "TextData" file format.
Included are a simple textdata_parser.py that converts the file to JSON, and a view_textdata.py that opens it in a pyQt6 GUI.
I also made a "hexview" program in python that lets you see the textdata_en.dat in a easier to read structure.

hex_to_ascii.py is a simple "hex to ascii" program that I used when experimenting with the text replacing.

string_newlines.py just adds a new line to every null terminated string.

textdata_generate.py is the failed text replace modding tool. It "works" but the offsets are broken.

# What TextData is
The game uses i18n, which replaces strings in the code with a LUT pointer, making it possible to support multiple languages with a simple "insert string from this language" approach.

wood_sword can just be "0x01" and so in the LUT
0x01 points to "Wooden Sword"

TextData is a binary file that contains a LUT (look up table)

And you can make that LUT for multiple languages, all having the same structure.


## File Layout

```
OFFSET       SIZE     FIELD
0x0000       4        Header (uint32 LE)
0x0004       11912    String Pointers (2978 entries x 4 bytes each)
0x2E8C       4        Sentinel (uint32 LE)
0x2E90       86211    String data region (null-terminated UTF-8/ASCII)
```

The game has two of these, the english one "textdata_en.dat" being the default.

# My Reverse Engineering
When I first started to decode this file, I did not know any of that.
All I knew is that all strings in the binary were "obfuscated" with getText() and that in order to know what the string was I had to find out how to "getText".

Using a simple hex editor, I manually looked at the hexadecimal bytes and their corresponding ASCII

```
0x0004 | 00 00 00 00
```
I think it took me about an hour before I figured out that the top part of the file had a sequential pattern and that each contained sequential offset "pointers" to the null terminated ASCII strings on the other half of the file.


| LUT file offset | Pointer value (LE) | Absolute address | String |
|-----------------|-------------------|------------------|--------|
| 0x0004 | `00 00 00 00` | 0x2E90 + 0x00000000 = 0x2E90 | `Accuracy :<CF3F300FF> High<CFFFFFFFF>` |
| 0x0FA0 | `9F 6B 00 00` | 0x2E90 + 0x00006B9F = 0x9A2F | `It's very hard substance, but easy to process, so commonly used to manufacture weapons.` |
| 0x1F40 | `2C DE 00 00` | 0x2E90 + 0x0000DE2C = 0x10CBC | `Weight Stone` |
| 0x2E88 | `B4 50 01 00` | 0x2E90 + 0x000150B4 = 0x17F44 | `Privacy Policy` |


That was about as much as I could gather. I also found that the last pointer was a "End of File" pointer, it didn't point at a starting string, it instead pointed at the byte after the end of the last string.

# End Results
Using this information I tried to vibe code a simple "parser" for textdata_en.dat, I was able to properly extract the strings into a neat pyQt6 GUI with right click to copy and search box filter features. But I also wanted to do the reverse, essentially making a string replacing modding tool that would let you rewrite any string in the game.

While it did sort of work, the byte offsets were off. When I tested it in-game there were many things that started and ended in-between two strings.

I still think it should be possible to make the "textdata string replacer" tool, but more research and manual testing must be done in order for it to work properly.

Further progress into this has been stopped since I already got everything I needed, with the simple textdata parser I was able to create a post process "string annotation" script that automatically de-obfuscated the decompiled code by adding a comment to each pointer variable with its actual string. With that I was finally able to reverse engineer the decompiled code and make a working "revival" patch to the game binary.

You can read the [tools/textdata_parser/TEXTDATA_INFO.md](https://raw.githubusercontent.com/420gaming420/darkness-survival-revival/dev/tools/textdata_parser/TEXTDATA_INFO.md) document for more in-depth information about the games "TextData".
