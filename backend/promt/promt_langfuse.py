from langfuse import Langfuse
import os
from dotenv import load_dotenv
import traceback

load_dotenv()

public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
secret_key = os.getenv("LANGFUSE_SECRET_KEY")
host = os.getenv("LANGFUSE_HOST")
# Khởi tạo SDK (API Key lấy trong Settings của Langfuse)

langfuse = Langfuse(
    public_key=public_key,
    secret_key=secret_key,
    host=host
)

# 1. Lấy prompt phiên bản 'production' từ Langfuse


# 2. Chuẩn bị dữ liệu biến thực tế
# variables = {
    # "summary": "null",
    # "recent_turns": [
    #     {"role": "user", "content": "Vẽ cho em đồ thị y = x^2 - 4x + 3"},
    #     {"role": "assistant", "content": "Đã vẽ đồ thị."}
    # ],
    # "canvas_objects": [
    #     {"id": "para_01", "kind": "parabola", "label": "y = x^2 - 4x + 3"}
    # ],
    # "current_question": "Tìm đỉnh của đồ thị đó giúp em."
# }

# # 3. Biên dịch (compile) prompt để chèn các biến vào template
# compiled_prompt = prompt.compile(**variables)

# print(compiled_prompt)
def get_prompt_langfuse(link, label, variables):
  

    try:
        

        prompt = langfuse.get_prompt(
            name=link,
            label=label
        )

        print("3 - prompt =", prompt)
        print("=== PROMPT NAME ===")
        print(prompt.name)

        print("=== PROMPT VERSION ===")
        print(prompt.version)

   

        print("=== PROMPT TEMPLATE ===")
        print(prompt.prompt)
        print("4 - compile")

        compiled_prompt = prompt.compile(**variables)

        print("5 - compiled :",dir(compiled_prompt))

        return compiled_prompt

    except Exception:
        traceback.print_exc()
        raise