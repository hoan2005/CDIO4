
def remove_object(self, task: dict, canvas_changes: dict) -> dict:
    """
    Lấy ID đối tượng cần xóa và đưa vào canvas.remove.
    """
    task_input = task.get("input", {})

    object_id = (
        task_input.get("object_id")
        or task.get("target_id")
    )

    if not object_id:
        raise ValueError(
            "Không tìm thấy object_id cần xóa."
        )

    canvas_changes["remove"].append(object_id)

    return {
        "task_id": task["id"],
        "status": "success",
        "operation": "remove_object",
        "result": object_id,
    }
