from unidecode import unidecode
try:
    import urdu2roman
    print("Urdu 'السلام علیکم':", urdu2roman.romanize("السلام علیکم"))
except ImportError:
    print("urdu2roman not found")

print("Arabic 'مرحبا' (unidecode):", unidecode("مرحبا"))
print("Arabic 'شكرا' (unidecode):", unidecode("شكرا"))
