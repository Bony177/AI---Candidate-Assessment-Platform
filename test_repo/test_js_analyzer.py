from pathlib import Path

from app.services.js_analyzer import analyze_javascript_file


files = {
    "sample.js": """
import React from "react";

export function hello(name) {
    if (name) {
        return "Hello " + name;
    }

    return "Hello";
}
""",

    "sample.jsx": """
import React from "react";

export function App() {
    return <div>Hello World</div>;
}
""",

    "sample.ts": """
import { add } from "./utils";

export function calculate(a: number, b: number): number {
    if (a > b) {
        return a + b;
    }

    return a - b;
}
""",

    "sample.tsx": """
import React from "react";

interface Props {
    name: string;
}

export function App({ name }: Props) {
    return <div>Hello {name}</div>;
}
""",
}


for filename, content in files.items():
    path = Path("test_repo") / filename
    path.write_text(content, encoding="utf-8")

    result = analyze_javascript_file(path)

    print(f"\n===== {filename} =====")
    print(result)