from pdf2image import convert_from_path
import pytesseract

# Convert PDF pages to images
pdf_file = "report.pdf"
images = convert_from_path(pdf_file)

# Extract text from images
text = ""
for image in images:
    text += pytesseract.image_to_string(image)

print(text)
