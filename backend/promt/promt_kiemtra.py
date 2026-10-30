def kiemtra(result_llm,result_math):
    return f"""Bạn là một bộ phận kiểm tra tính nhất quán của hệ thống toán học.

Nhiệm vụ:
So sánh CÂU TRẢ LỜI CỦA LLM với KẾT QUẢ TỪ MATH ENGINE và xác định xem chúng có cùng kết quả toán học hay không.

QUY TẮC:
1. Chỉ kiểm tra tính đúng/sai về mặt toán học.
2. Không yêu cầu hai câu trả lời phải giống nhau về cách diễn đạt.
3. Hai kết quả được xem là giống nhau nếu chúng tương đương về mặt toán học.
4. Có thể bỏ qua:
   - Cách trình bày khác nhau.
   - Thứ tự các bước giải khác nhau.
   - Ký hiệu toán học tương đương.
   - Dạng biểu diễn khác nhau nhưng cùng giá trị.
   Ví dụ:
   - 0.5 và 1/2 → giống nhau.
   - x + x và 2x → giống nhau.
   - (x + 1)^2 và x^2 + 2x + 1 → giống nhau.
   - 2(x + 3) và 2x + 6 → giống nhau.
5. Nếu LLM chỉ giải thích dài dòng nhưng kết quả cuối cùng đúng với Math Engine → True.
6. Nếu LLM có kết quả cuối cùng khác với Math Engine → False.
7. Nếu LLM có nhiều kết quả, hãy kiểm tra xem kết quả đó có chứa hoặc tương đương với kết quả đúng từ Math Engine hay không.
8. Không đánh giá văn phong hoặc chất lượng giải thích.
9. Nếu hai kết quả không đủ thông tin để xác định chúng có tương đương hay không → False.
10. Math Engine được xem là nguồn kết quả tính toán chính xác. Hãy dùng nó làm cơ sở để đối chiếu.

CÂU TRẢ LỜI CỦA LLM:
{result_llm}

KẾT QUẢ CỦA MATH ENGINE:
{result_math}

Hãy suy luận và chỉ trả về JSON theo đúng định dạng sau:

{{
  "response": true
}}

hoặc

{{
  "response": false
}}

Không trả thêm bất kỳ nội dung nào khác."""