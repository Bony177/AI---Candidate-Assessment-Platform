
import { add } from "./utils";

export function calculate(a: number, b: number): number {
    if (a > b) {
        return a + b;
    }

    return a - b;
}
