import CodeMirror from "@uiw/react-codemirror";
import { json, jsonParseLinter } from "@codemirror/lang-json";
import { linter, lintGutter } from "@codemirror/lint";
import { githubDark, githubLight } from "@uiw/codemirror-theme-github";
import { useEffectiveTheme } from "../../lib/theme";

// Default export + lazy-loaded so CodeMirror is a separate chunk (only fetched
// when the user opens the raw-JSON view).
export default function RawJsonEditor({
  value, onChange,
}: {
  value: string;
  onChange: (t: string) => void;
}) {
  const isDark = useEffectiveTheme() === "dark";
  return (
    <CodeMirror
      className="cm-fill"
      value={value}
      onChange={onChange}
      theme={isDark ? githubDark : githubLight}
      extensions={[json(), linter(jsonParseLinter()), lintGutter()]}
      basicSetup={{
        lineNumbers: true,
        foldGutter: true,
        bracketMatching: true,
        highlightActiveLine: true,
        closeBrackets: true,
        autocompletion: false,
      }}
      height="100%"
    />
  );
}
