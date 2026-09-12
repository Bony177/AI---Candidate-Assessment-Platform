from pathlib import Path

from app.services.js_smells import detect_javascript_code_smells


# ==================================================
# TEST 1 — TOO MANY PARAMETERS
# ==================================================

too_many_params = Path("test_repo/smelly_parameters.js")

too_many_params.write_text(
    """
function badFunction(a, b, c, d, e, f) {
    return a + b + c + d + e + f;
}
""",
    encoding="utf-8",
)


print("\n===== TOO MANY PARAMETERS =====")

result = detect_javascript_code_smells(too_many_params)

for finding in result:
    print(finding)


# ==================================================
# TEST 2 — LONG FUNCTION
# ==================================================

long_function = Path("test_repo/smelly_long.js")

long_function_body = "\n".join(
    f"    const value{i} = {i};"
    for i in range(55)
)

long_function.write_text(
    f"""
function veryLongFunction() {{
{long_function_body}
    return value54;
}}
""",
    encoding="utf-8",
)


print("\n===== LONG FUNCTION =====")

result = detect_javascript_code_smells(long_function)

for finding in result:
    print(finding)


# ==================================================
# TEST 3 — LARGE FILE
# ==================================================

large_file = Path("test_repo/smelly_large.js")

large_file.write_text(
    "\n".join(
        f"const value{i} = {i};"
        for i in range(301)
    ),
    encoding="utf-8",
)


print("\n===== LARGE FILE =====")

result = detect_javascript_code_smells(large_file)

for finding in result:
    print(finding)


# ==================================================
# TEST 4 — HIGH COMPLEXITY
# ==================================================

high_complexity = Path("test_repo/smelly_complex.js")

high_complexity.write_text(
    """
function complexFunction(a, b, c, d, e, f) {

    if (a) {
        if (b) {
            if (c) {
                if (d) {
                    if (e) {
                        if (f) {
                            return true;
                        }
                    }
                }
            }
        }
    }

    for (let i = 0; i < 10; i++) {
        if (i > 5) {
            while (i > 8) {
                break;
            }
        }
    }

    try {
        console.log("test");
    } catch (error) {
        console.log(error);
    }

    return a ? b : c;
}
""",
    encoding="utf-8",
)


print("\n===== HIGH COMPLEXITY =====")

result = detect_javascript_code_smells(high_complexity)

for finding in result:
    print(finding)