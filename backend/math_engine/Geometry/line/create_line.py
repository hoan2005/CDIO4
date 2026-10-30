import uuid
def generate_id():
    return uuid.uuid4().hex
def create_line_2d(point1, point2):

    x1, y1 = point1
    x2, y2 = point2

    A = y1 - y2
    B = x2 - x1
    C = x1 * y2 - x2 * y1

    return {
        "id": generate_id(),
        "kind": "line",
        "dimension": "2d",
        "points": [
                point1,
                point2
            ],

        "equation": f"{A}x + {B}y + {C} = 0",

            "parameters": {
                "A": A,
                "B": B,
                "C": C
            }
        }
  