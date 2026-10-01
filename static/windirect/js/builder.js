/* افزودن امن ردیف‌های فرم‌ست؛ اعتبارسنجی اصلی در سرور انجام می‌شود. */
document.querySelectorAll('[data-formset]').forEach((root) => {
    const total = document.getElementById('id_items-TOTAL_FORMS');
    const add = root.querySelector('[data-add]');
    root.addEventListener('change', (event) => {
        if (!event.target.matches('[name$="-DELETE"]')) return;
        event.target.closest('fieldset').querySelectorAll('input, textarea, select').forEach((field) => {
            if (field === event.target || field.type === 'hidden') return;
            if (event.target.checked) {
                field.dataset.wasRequired = String(field.required);
                field.required = false;
            } else {
                field.required = field.dataset.wasRequired === 'true';
            }
        });
    });
    add.addEventListener('click', () => {
        const index = Number(total.value);
        const limit = Number(root.dataset.limit);
        if (index >= limit) {
            root.querySelector('[data-formset-status]').textContent = 'به سقف موارد رسیدید. حذف‌ها را ذخیره کنید و سپس مورد جدید اضافه کنید.';
            return;
        }
        const template = root.querySelector('[data-empty]');
        const holder = document.createElement('template');
        holder.innerHTML = template.innerHTML.replaceAll('__prefix__', String(index));
        const position = holder.content.querySelector('[name$="-position"]');
        const positions = [...root.querySelectorAll('[name$="-position"]')].map((field) => Number(field.value) || 0);
        if (position) position.value = Math.max(0, ...positions) + 1;
        root.querySelector('[data-items]').append(holder.content);
        total.value = index + 1;
        const last = root.querySelector('[data-items]').lastElementChild;
        last.querySelector('input:not([type="hidden"]), textarea, select')?.focus();
        root.querySelector('[data-formset-status]').textContent = 'مورد جدید اضافه شد.';
    });
});
