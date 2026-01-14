# Romanization Support Walkthrough

I have implemented support for romanization in the TTML to JSON conversion pipeline.

## Features
1. **TTML to JSON Conversion**: `ttml_to_json.py` now reads `x-roman` attributes from TTML `<p>` and `<span>` tags and outputs them as `roman` fields in the JSON.
2. **Auto-Romanization Tool**: `add_romanization.py` supports multiple languages.
3. **Background Vocals**: Recursively romanized.
4. **Translation Handling**: Spans with `role="x-translation"` are **automatically ignored** during romanization to prevent duplication or incorrect text.

## Supported Languages & Requirements
You need to install the respective libraries for the languages you want to process:

- **Korean (`kor`)**: `pip install korean-romanizer`
- **Japanese (`jpn`)**: `pip install pykakasi`
- **Chinese (`chi`/`zho`)**: `pip install pypinyin`
- **Hindi (`hin`)**: `pip install indic-transliteration`
- **Urdu (`urd`)**: `pip install urdu2roman` (or `unidecode` as fallback)
- **Arabic (`ara`)**: `pip install unidecode`

## Usage

### 1. Auto-generate Romanization
Specify the language using `--lang` code:
```bash
# Japanese
python add_romanization.py file.ttml --lang jpn

# Arabic
python add_romanization.py file.ttml --lang ara
```

### 2. Convert to JSON
```bash
python ttml_to_json.py file.ttml
```

## Example Output
**Input TTML (with Translation):**
```xml
<p x-roman="konnichiha">
  <span x-roman="konnichiha">こんにちは</span>
  <span role="x-translation">Hello</span>
</p>
```
The translation "Hello" is correctly excluded from the romanization "konnichiha".
