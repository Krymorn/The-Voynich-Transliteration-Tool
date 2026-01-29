# The Voynich Transliteration Tool (TVTT)
**Version 1.6.2**

Create your own Voynich Manuscript transliteration based on the v101 transcription.

## Overview
TVTT is a cryptographic workbench that replaces each character in the v101 transcription of the Voynich Manuscript with a customizable, user-defined mapping. 

Beyond simple transliteration, the tool acts as a testing ground for decipherment theories. It performs **deep statistical verification**—including Zipf's Law analysis, Entropy calculation, and Sukhotin's vowel detection—to determine if your mapping behaves like a natural language or random noise. It also supports **Dialect Sectioning**, allowing you to isolate and test specific "languages" (e.g. Currier A vs. B) within the manuscript.

## Features
- **Positional Context Mapping:** Distinct rules for characters at the start (`@`), end (`/`), or middle of words.
- **Occurrence Mapping:** Specific rules for the 1st, 2nd, 3rd, or 4th time a character appears in a word (using `'`, `"`, `:`, `;`).
- **Multi-character Mapping:** Map one input character to many (e.g., `53=9~con`) or many input characters to one (e.g., `101=4o~d`).
- **Dialect Sectioning:** Restrict processing to specific line ranges to isolate "Currier A" (Herbal) or "Currier B" (Biological) dialects.
- **Corpus Analysis ("The Combinator"):** A post-processing engine that compares your output against real dictionaries.
  - **Fuzzy Matching:** Corrects "typos" using Dynamic Strictness (strict for short words, looser for long words).
  - **Word Merging:** Detects and fixes segmentation errors (e.g., merging "in" + "to" -> "into").
- **Translation Module:** Attempt to automatically translate your output into English (via Google Translate) to check for intelligible sentences.
- **Deep Statistical Analysis:**
  - **Entropy Calculation:** Measures the randomness of your output.
  - **Sukhotin Vowel Analysis:** Algorithmically predicts vowels based on character adjacency.
  - **Reduplication Detection:** Verifies if your mapping preserves the manuscript's frequent word repetition (e.g., *chol chol*).
  - **Zipf's Law Visualization:** Generates a log-log plot to compare your text's frequency distribution against natural language laws.
- **HTML Comparison Report:** Generates a side-by-side visual report (`comparison.html`) of the original text vs. your transliteration.

### Performance Warning: Fuzzy Matching
**Please Read Before Running:**
The **Corpus Analysis / Fuzzy Matching** feature is extremely computationally intensive. It compares every word in the manuscript (approx. 35,000 words) against every word in your reference dictionary using complex similarity algorithms.

* **The Cost:** Running the full manuscript against a large dictionary can take **hours**.
* **The Solution:** Do not run the full text immediately. Open `main.py` and set the `endLine` variable to a small number (e.g., `endLine = 200`) to test your settings on a small chunk first. 
* **To run the full text:** Only set `endLine = None` when you are satisfied with your settings and ready to wait.

## Tutorial

### File Structure
- `cleaner.py`: Cleans the raw `v101.txt` and saves it to `v101_cleaned.txt`.
- `mapping.py`: Scans the cleaned text to auto-populate `mapping.txt` with all unique characters found.
- `mapping.txt`: The core configuration file where you define your substitution rules.
- `main.py`: Reads `mapping.txt`, processes the text, and generates all outputs.
- `reference_texts/`: A folder where you place `.txt` dictionaries (e.g. `latin.txt`) for the fuzzy matcher to use.
- `output.txt`: The final transliterated text (uses underscores `_` for spaces).
- `output_fuzzy.txt`: The transliterated text **after** being auto-corrected by the Corpus Analysis.
- `discovery_report.txt`: A report listing every word merge and typo correction found by the system.
- `output_numbers.txt`: A debug file showing the numerical IDs used during processing.
- `analysis.txt`: Statistical data (Frequency, Entropy, Affixes, Vowel predictions, Reduplication).
- `zipf_analysis.png`: A graph visualizing word frequency.
- `comparison.html`: A visual report comparing source vs. output line-by-line.
- `translated.txt`: (Optional) The machine-translated version of your output.

**NOTE:** Do not edit `v101.txt` or `v101_cleaned.txt` manually.

### Syntax for `mapping.txt`
- **`@`** — End of line: Use this mapping only if the character is at the **start** of a word (e.g., `56=9~s@`).
- **`/`** — End of line: Use this mapping only if the character is at the **end** of a word (e.g., `57=9~us/`).
- **`'`**, **`"`**, **`:`**, **`;`** — Use these for the 1st, 2nd, 3rd, and 4th **occurrence** of a character within a single word.
- **`)`** — Start of line: Comment out the line (ignore it). Lines with incorrect syntax will also be ignored.
- **No Symbol** — Provided mapping will be used if no positional rule matches.

### Instructions
1.  **Install:** Download the source code from the latest release. Ensure you have Python installed.
    * *Optional (But recommended):* Install dependencies for graphs/translation: `pip install matplotlib deep-translator numpy`
    
2.  **Configure:** Open `main.py` to adjust settings:
    * **CRITICAL:** Set `endLine = 200` initially to test without waiting hours.
    * Set `startLine` and `endLine` to test specific sections (e.g., 0-700 for Herbal Section) or leave `endline` as `None` to continue until the end of the input file.
    * Toggle `enableCorpusAnalysis` to True if you want to use the fuzzy matcher.
    * Toggle `enableHTMLComparison` or `enableZipfsLawGeneration` as needed.
    * Set `enableTranslation = True` if you want to attempt Google Translate on your output.
    
3.  **Setup References:** If using Corpus Analysis, find a text file of a dictionary (e.g. `latin.txt`) and place it inside the `reference_texts` folder.

4.  **Map:** Edit `mapping.txt` to define your substitution cipher.

5.  **Run:** Execute `main.py`. (Run `python main.py` in Terminal/Command Line)

6.  **Analyze:** Review `output.txt`, `output_fuzzy.txt`, `analysis.txt`, `zipf_analysis.png`, and `comparison.html`.

## Troubleshooting & FAQ

#### **CRITICAL: "Why does `comparison.html` look unchanged?"**
**Browser Caching Issue:** If you run the script and `comparison.html` still shows your old results (or the original text), your web browser is likely loading a cached version of the file.
* **Fix:** With the HTML file open in your browser, perform a **Hard Refresh** by pressing `Ctrl + F5` (Windows) or `Cmd + Shift + R` (Mac). This forces the browser to reload the actual file from the disk.

**Q: Can I map multiple input characters to a single letter?**
A: Yes. The tool supports multi-character inputs (n-graphs).
* *Example:* `101=4o~d` (This tells the tool to treat every instance of the sequence "4o" as the letter "d").
* The tool prioritizes the longest matches first, so if you have mappings for both `4` and `4o`, it will correctly identify `4o` as a single unit before falling back to `4`.

**Q: Can I map one Voynich character to multiple letters?**
A: Yes.
* *Example:* `53=9~con` (This maps the single symbol `9` to the string `con`).

**Q: What are Currier A and Currier B?**
A: These are the two distinct "languages" or "hands" in the manuscript. You can use the `startLine` and `endLine` variables in `main.py` to test your mapping on just one section at a time (e.g., lines 1–700 for Currier A/Herbal).

**Q: Why is "Reduplication" analysis included?**
A: The Voynich manuscript features frequent immediate repetition (e.g., *chol chol*). If your mapping turns this into something unnatural like *the the*, it may be incorrect. This feature helps verify if your mapping preserves this structural feature.

**Q: What does the Zipf's Law graph show?**
A: Natural languages follow a specific slope where the most common word is twice as frequent as the second, etc. If the "Ideal" line and your "Data" points are wildly different, your output may be gibberish rather than language.

**Q: Where can I get a v101 transliteration reference?**
A: [Voynich.nu](https://www.voynich.nu/transcr.html) has excellent reference charts.

## Planned Features
- Batch processing of multiple texts for comparison.
- Morphological decomposition tools.
- Multi-language dictionary assisted mapping suggestions.
- Option to use EVA or an alternative transcription.

## Credits & Citations
1.  **Voynich.nu** for the [v101 transcription](https://voynich.nu/data/voyn_101.txt).<br>
2.  **ChatGPT** for assistance with word part analysis logic.<br>
3.  **Google Gemini** for `cleaner.py`, statistical algorithms (Sukhotin/Zipf), and structural improvements.<br>
4.  **deep-translator** Python library for the translation module.<br>
