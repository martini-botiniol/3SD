"""Small reader for Steam's quoted KeyValues files; never executes content."""
import re


def parseVdf(text: str) -> dict:
    tokens = re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])|(?://[^\n]*)', text)
    values = []
    for token in tokens:
        quoted, brace = token.groups()
        if quoted is not None:
            values.append(re.sub(r'\\([\\"])', r'\1', quoted))
        elif brace is not None:
            values.append(brace)
    iterator = iter(values)

    def objectValue(nested=False):
        result = {}
        for key in iterator:
            if key == "}":
                if not nested:
                    raise ValueError("Unexpected closing brace")
                return result
            value = next(iterator)
            if value == "}" or key == "{":
                raise ValueError("Unexpected brace")
            result[key] = objectValue(True) if value == "{" else value
        if nested:
            raise ValueError("Unclosed object")
        return result

    try:
        return objectValue()
    except (StopIteration, RecursionError) as exc:
        raise ValueError("Invalid KeyValues") from exc
