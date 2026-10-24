REQUIRED_ERROR_TEMPLATE = "Заповніть поле «{label}»."


def apply_required_error_messages(form):
    for field in form.fields.values():
        if field.required:
            label = (field.label or "це поле").strip()
            field.error_messages["required"] = REQUIRED_ERROR_TEMPLATE.format(label=label)
