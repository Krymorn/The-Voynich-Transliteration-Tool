import re
import argparse
import sys


def clean_transcription(text):
  """
  - Removes anything between < and > (including the symbols)
  - Replaces all periods with equal signs and commas with dashes
  """

  # Remove everything between < and >
  text = re.sub(r"<[^>]*>", "", text)

  # Remove - and = characters which typically mark the end of a line in the v101 transcription but are unnecessary here
  text = text.replace("-", "")
  text = text.replace("=", "")
  
  # Replace periods with equal signs
  text = text.replace(".", "=")

  # Replace commas with dashes
  text = text.replace(",", "-")

  return text


def process_file(input_path, output_path):
  try:
      with open(input_path, "r", encoding="utf-8") as file:
          raw_text = file.read()
  except FileNotFoundError:
      print(f"ERROR: File not found: {input_path}")
      sys.exit(1)
  except Exception as e:
      print(f"ERROR reading file: {e}")
      sys.exit(1)

  cleaned_text = clean_transcription(raw_text)

  try:
      with open(output_path, "w", encoding="utf-8") as file:
          file.write(cleaned_text)

      print("\n✅ File cleaned successfully!")
      print(f"Input : {input_path}")
      print(f"Output: {output_path}\n")

  except Exception as e:
      print(f"ERROR writing file: {e}")
      sys.exit(1)


def main():
  parser = argparse.ArgumentParser(
      description="Clean Voynich v101 transcription by removing < > content and replacing . with #"
  )

  parser.add_argument("input_file", help="Input file (example: v101.txt)")
  parser.add_argument("output_file", help="Output file (example: v101_cleaned.txt)")

  args = parser.parse_args()

  process_file(args.input_file, args.output_file)

# Run main
if __name__ == "__main__":
  main()
