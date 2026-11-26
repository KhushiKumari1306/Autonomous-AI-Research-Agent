import ast
import operator
from tavily import TavilyClient

from config import TAVILY_API_KEY


# Initialize web search client
tavily = TavilyClient(api_key=TAVILY_API_KEY)


# ---------------------------
# TOOL 1: WEB SEARCH
# ---------------------------

def web_search(query: str) -> str:
    """
    Search the internet for information.
    """

    try:
        response = tavily.search(
            query=query,
            max_results=5
        )

        results = response.get("results", [])

        if not results:
            return "No search results found."

        formatted_results = []

        for result in results:
            formatted_results.append(
                f"""
Title: {result.get('title', 'No title')}

URL: {result.get('url', '')}

Content: {result.get('content', '')}
"""
            )

        return "\n".join(formatted_results)

    except Exception as e:
        raise RuntimeError(f"Web search failed: {str(e)}")


# ---------------------------
# TOOL 2: CALCULATOR
# ---------------------------

_ALLOWED_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def calculator(expression: str):
    """
    Safely evaluate basic mathematical expressions.
    """

    def evaluate(node):

        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value

        elif isinstance(node, ast.BinOp):
            operator_type = type(node.op)

            if operator_type in _ALLOWED_OPERATORS:
                left = evaluate(node.left)
                right = evaluate(node.right)

                # Prevent excessively large exponent calculations
                if isinstance(node.op, ast.Pow) and abs(right) > 10:
                    raise ValueError("Exponent too large.")

                return _ALLOWED_OPERATORS[operator_type](
                    left, right
                )

        elif isinstance(node, ast.UnaryOp):
            operator_type = type(node.op)

            if operator_type in _ALLOWED_OPERATORS:
                return _ALLOWED_OPERATORS[operator_type](
                    evaluate(node.operand)
                )

        raise ValueError("Invalid mathematical expression.")

    try:
        parsed_expression = ast.parse(
            expression,
            mode="eval"
        )

        return evaluate(parsed_expression.body)

    except Exception as e:
        raise RuntimeError(
            f"Calculator failed: {str(e)}"
        )


# ---------------------------
# TOOL 3: REPORT WRITER
# ---------------------------

def save_report(content: str, filename: str = "report.md") -> str:
    """
    Save generated report to outputs folder.
    """

    import os

    output_directory = "outputs"

    os.makedirs(output_directory, exist_ok=True)

    # Prevent unsafe filenames/path traversal
    filename = os.path.basename(filename)

    if not filename.endswith(".md"):
        filename += ".md"

    filepath = os.path.join(
        output_directory,
        filename
    )

    with open(filepath, "w", encoding="utf-8") as file:
        file.write(content)

    return f"Report successfully saved at: {filepath}"