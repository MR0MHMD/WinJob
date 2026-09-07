def number_to_words(amount, currency='ریال'):
    """
    تبدیل عدد به حروف فارسی به صورت کامل
    """
    if amount == 0:
        return "صفر"

    # تبدیل عدد به لیست ارقام
    num_str = str(amount)
    length = len(num_str)

    # جدا کردن بخش‌های ۳ رقمی از سمت راست
    chunks = []
    while length > 0:
        if length >= 3:
            chunks.append(int(num_str[length - 3:length]))
        else:
            chunks.append(int(num_str[0:length]))
        length -= 3

    # برعکس کردن لیست برای پردازش از بزرگترین بخش
    chunks = chunks[::-1]

    # کلمات پایه
    ones = ["", "یک", "دو", "سه", "چهار", "پنج", "شش", "هفت", "هشت", "نه"]
    teens = ["ده", "یازده", "دوازده", "سیزده", "چهارده", "پانزده", "شانزده", "هفده", "هجده", "نوزده"]
    tens = ["", "", "بیست", "سی", "چهل", "پنجاه", "شصت", "هفتاد", "هشتاد", "نود"]
    hundreds = ["", "یکصد", "دویست", "سیصد", "چهارصد", "پانصد", "ششصد", "هفتصد", "هشتصد", "نهصد"]

    # نام بخش‌ها
    section_names = ["", "هزار", "میلیون", "میلیارد", "همت"]

    def convert_chunk(num):
        """تبدیل یک بخش ۳ رقمی به حروف"""
        result = []

        h = num // 100
        t = (num % 100) // 10
        o = num % 10

        if h > 0:
            result.append(hundreds[h])

        if t == 1:
            result.append(teens[o])
        else:
            if t > 1:
                result.append(tens[t])
            if o > 0:
                result.append(ones[o])

        return " و ".join(result)

    # ترکیب بخش‌ها
    result_parts = []
    for i, chunk in enumerate(chunks):
        if chunk > 0:
            part_text = convert_chunk(chunk)
            if section_names[len(chunks) - 1 - i]:
                part_text += " " + section_names[len(chunks) - 1 - i]
            result_parts.append(part_text)

    # اتصال نهایی با "و"
    words = " و ".join(result_parts)

    # اضافه کردن واحد پول
    return f"{words} {currency}"
