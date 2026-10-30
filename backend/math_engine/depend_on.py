import re


def resolve_reference(
    value,
    task_results: dict
):
    # Nếu không phải reference thì giữ nguyên
    if not isinstance(value, str):
        return value

    # Không phải chuỗi reference
    if not value.startswith("$"):
        return value

    # Bỏ dấu $
    path = value[1:]

    # Ví dụ:
    # task_1.result.solutions[0]

    parts = re.findall(
        r'([a-zA-Z_][a-zA-Z0-9_]*)|\[(\d+)\]',
        path
    )

    current = task_results

    for key, index in parts:

        if key:
            current = current[key]

        elif index:
            current = current[int(index)]

    return current