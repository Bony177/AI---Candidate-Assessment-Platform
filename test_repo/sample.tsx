
import React from "react";

interface Props {
    name: string;
}

export function App({ name }: Props) {
    return <div>Hello {name}</div>;
}
