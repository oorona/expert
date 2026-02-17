"use client";

// Color palette (matches JsonEditor theme)
const C = {
  keyword:  "#7dd3fc", // blue
  string:   "#86efac", // green
  number:   "#c084fc", // purple
  comment:  "#6b7280", // gray
  builtin:  "#fbbf24", // amber  (booleans, shell commands)
  variable: "#f87171", // red    (null, shell vars)
  type:     "#67e8f9", // cyan   (types, decorators)
  operator: "#94a3b8", // slate  (punctuation)
};

function span(color: string, text: string) {
  return `<span style="color:${color}">${text}</span>`;
}

function escapeHtml(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

// ---------------------------------------------------------------------------
// Language highlighters — single-pass regex, priority: comment > string > ...
// ---------------------------------------------------------------------------

function highlightSql(code: string): string {
  return escapeHtml(code).replace(
    /(--[^\n]*|\/\*[\s\S]*?\*\/)|('(?:[^'\\]|\\.)*')|(\b\d+(?:\.\d+)?\b)|\b(SELECT|FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|FULL|ON|AND|OR|NOT|IN|IS|NULL|AS|ORDER|BY|ASC|DESC|GROUP|HAVING|LIMIT|OFFSET|FETCH|INSERT|INTO|VALUES|UPDATE|SET|DELETE|MERGE|CREATE|TABLE|VIEW|INDEX|SEQUENCE|TRIGGER|PROCEDURE|FUNCTION|SCHEMA|DATABASE|DROP|ALTER|ADD|COLUMN|PRIMARY|FOREIGN|UNIQUE|KEY|REFERENCES|CONSTRAINT|DEFAULT|CHECK|CASCADE|RESTRICT|TRUNCATE|BEGIN|COMMIT|ROLLBACK|SAVEPOINT|TRANSACTION|GRANT|REVOKE|WITH|UNION|ALL|DISTINCT|CASE|WHEN|THEN|ELSE|END|EXISTS|BETWEEN|LIKE|ILIKE|CAST|COALESCE|NULLIF|NVL|DECODE|COUNT|SUM|AVG|MIN|MAX|ROW_NUMBER|RANK|DENSE_RANK|LAG|LEAD|PARTITION|OVER|EXPLAIN|ANALYZE|EXECUTE|CALL|RETURNING|DO|LOOP|RAISE|EXCEPTION|DECLARE|BEGIN|END|LANGUAGE|PLPGSQL|INTEGER|VARCHAR|TEXT|BOOLEAN|DATE|TIMESTAMP|NUMBER|FLOAT|CLOB|BLOB|RAW|ROWID|SYSDATE|SYSTIMESTAMP|TRUE|FALSE)\b/gi,
    (match, comment, str, num, keyword) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match.toUpperCase());
      return match;
    }
  );
}

function highlightJs(code: string): string {
  return escapeHtml(code).replace(
    /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|((?:`(?:[^`\\]|\\.)*`|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'))|\b(\d+(?:\.\d+)?(?:e[+-]?\d+)?(?:n)?)\b|\b(abstract|as|async|await|break|case|catch|class|const|constructor|continue|debugger|declare|default|delete|do|else|enum|export|extends|finally|for|from|function|get|if|implements|import|in|instanceof|interface|let|module|namespace|new|null|of|override|package|private|protected|public|readonly|return|set|static|super|switch|this|throw|try|type|typeof|undefined|var|void|while|with|yield|true|false)\b/g,
    (match, comment, str, num, keyword) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match);
      return match;
    }
  );
}

function highlightPython(code: string): string {
  return escapeHtml(code).replace(
    /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(\d+(?:\.\d+)?(?:j)?)\b|(@\w+)|\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|finally|for|from|global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|return|try|while|with|yield|None|True|False)\b|\b(int|str|float|bool|list|dict|tuple|set|bytes|bytearray|type|object|Exception|ValueError|TypeError|KeyError|IndexError|AttributeError|ImportError|OSError|len|range|print|input|open|enumerate|zip|map|filter|sorted|reversed|isinstance|issubclass|super|property|staticmethod|classmethod|abs|round|min|max|sum|any|all)\b/g,
    (match, comment, str, num, decorator, keyword, builtin) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (decorator !== undefined) return span(C.type, match);
      if (keyword !== undefined) return span(C.keyword, match);
      if (builtin !== undefined) return span(C.builtin, match);
      return match;
    }
  );
}

function highlightBash(code: string): string {
  return escapeHtml(code).replace(
    /(#[^\n]*)|(["'](?:[^"'\\]|\\.)*["'])|(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)|(\b\d+\b)|\b(if|then|else|elif|fi|for|do|done|while|until|case|esac|function|return|exit|break|continue|local|export|source|shift|set|unset|readonly|true|false)\b|\b(echo|printf|cd|ls|pwd|mkdir|rm|cp|mv|cat|grep|sed|awk|cut|sort|uniq|wc|head|tail|find|xargs|tr|tee|curl|wget|ssh|scp|git|docker|kubectl|npm|pip|python|python3|ruby|perl|java|node|bash|sh|zsh|sudo|chmod|chown|chgrp|ln|touch|date|ps|kill|killall|which|type|alias|unalias|history|read|test|eval|exec|env|printenv|nohup|jobs|bg|fg|trap|wait)\b/g,
    (match, comment, str, variable, num, keyword, builtin) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (variable !== undefined) return span(C.variable, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match);
      if (builtin !== undefined) return span(C.builtin, match);
      return match;
    }
  );
}

function highlightJson(code: string): string {
  return escapeHtml(code).replace(
    /("(?:[^"\\]|\\.)*"(?:\s*:)?|true|false|null|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|[{}[\],:])/g,
    (match) => {
      if (/^"/.test(match)) return /:$/.test(match) ? span(C.keyword, match) : span(C.string, match);
      if (/^(true|false)$/.test(match)) return span(C.builtin, match);
      if (match === "null") return span(C.variable, match);
      if (/^-?\d/.test(match)) return span(C.number, match);
      return span(C.operator, match);
    }
  );
}

function highlightGo(code: string): string {
  return escapeHtml(code).replace(
    /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|(["'`](?:[^"'`\\]|\\.)*["'`])|\b(\d+(?:\.\d+)?)\b|\b(break|case|chan|const|continue|default|defer|else|fallthrough|for|func|go|goto|if|import|interface|map|package|range|return|select|struct|switch|type|var|nil|true|false)\b|\b(string|int|int8|int16|int32|int64|uint|uint8|uint16|uint32|uint64|float32|float64|complex64|complex128|byte|rune|bool|error|make|new|len|cap|append|copy|delete|close|panic|recover|print|println|fmt|os|io|http|json|sync|context|errors|strings|strconv)\b/g,
    (match, comment, str, num, keyword, builtin) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match);
      if (builtin !== undefined) return span(C.builtin, match);
      return match;
    }
  );
}

function highlightJava(code: string): string {
  return escapeHtml(code).replace(
    /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|(["'](?:[^"'\\]|\\.)*["'])|\b(\d+(?:\.\d+)?[lLfFdD]?)\b|\b(abstract|assert|break|case|catch|class|const|continue|default|do|else|enum|extends|final|finally|for|goto|if|implements|import|instanceof|interface|native|new|null|package|private|protected|public|return|static|strictfp|super|switch|synchronized|this|throw|throws|transient|try|var|void|volatile|while|true|false)\b|\b(String|Integer|Long|Double|Float|Boolean|Object|Class|List|Map|Set|ArrayList|HashMap|HashSet|System|Math|StringBuilder|Exception|RuntimeException|Thread|Runnable|Optional|Stream|Collections|Arrays|Scanner|File|Path|Paths|Files|int|long|double|float|boolean|char|byte|short)\b/g,
    (match, comment, str, num, keyword, builtin) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match);
      if (builtin !== undefined) return span(C.type, match);
      return match;
    }
  );
}

function highlightCsharp(code: string): string {
  return escapeHtml(code).replace(
    /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|([@$]?"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')|\b(\d+(?:\.\d+)?[mMfFlLuU]?)\b|\b(abstract|as|base|break|case|catch|checked|class|const|continue|default|delegate|do|else|enum|event|explicit|extern|finally|fixed|for|foreach|goto|if|implicit|in|interface|internal|is|lock|namespace|new|null|object|operator|out|override|params|private|protected|public|readonly|ref|return|sealed|sizeof|stackalloc|static|struct|switch|this|throw|try|typeof|unchecked|unsafe|using|virtual|void|volatile|while|true|false|var|async|await|dynamic|get|set|value|yield|nameof|when|with|record|init)\b|\b(string|int|long|double|float|bool|char|byte|decimal|uint|ulong|ushort|sbyte|short|nint|nuint|String|Int32|Int64|Double|Boolean|Char|Byte|Object|Exception|List|Dictionary|IEnumerable|IList|Task|Console|Math|DateTime|Guid|Enum|Array|Nullable)\b/g,
    (match, comment, str, num, keyword, builtin) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (num !== undefined) return span(C.number, match);
      if (keyword !== undefined) return span(C.keyword, match);
      if (builtin !== undefined) return span(C.type, match);
      return match;
    }
  );
}

function highlightYaml(code: string): string {
  return escapeHtml(code).replace(
    /(#[^\n]*)|(["'](?:[^"'\\]|\\.)*["'])|(\b(?:true|false|null|~)\b)|(\b\d+(?:\.\d+)?\b)|(^[ \t]*[\w-]+(?=\s*:))/gm,
    (match, comment, str, bool, num, key) => {
      if (comment !== undefined) return span(C.comment, match);
      if (str !== undefined) return span(C.string, match);
      if (bool !== undefined) return span(C.builtin, match);
      if (num !== undefined) return span(C.number, match);
      if (key !== undefined) return span(C.keyword, match);
      return match;
    }
  );
}

// ---------------------------------------------------------------------------
// Dispatcher
// ---------------------------------------------------------------------------

function applyHighlight(code: string, lang: string): string {
  switch (lang.toLowerCase()) {
    case "sql":
    case "plsql":
    case "pgsql":
    case "mysql":
    case "tsql":
      return highlightSql(code);
    case "js":
    case "javascript":
    case "ts":
    case "typescript":
    case "jsx":
    case "tsx":
      return highlightJs(code);
    case "py":
    case "python":
      return highlightPython(code);
    case "bash":
    case "sh":
    case "shell":
    case "zsh":
      return highlightBash(code);
    case "json":
      return highlightJson(code);
    case "go":
    case "golang":
      return highlightGo(code);
    case "java":
      return highlightJava(code);
    case "cs":
    case "csharp":
    case "c#":
      return highlightCsharp(code);
    case "yaml":
    case "yml":
      return highlightYaml(code);
    default:
      return escapeHtml(code);
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  code: string;
  language?: string;
}

export function CodeBlock({ code, language = "" }: Props) {
  const highlighted = language ? applyHighlight(code, language) : escapeHtml(code);

  return (
    <div className="my-4 rounded-lg overflow-hidden border border-gray-700">
      {language && (
        <div className="flex items-center px-4 py-1.5 bg-gray-800 border-b border-gray-700">
          <span className="text-xs text-gray-400 font-mono uppercase tracking-wide">{language}</span>
        </div>
      )}
      <pre
        style={{
          background: "#0f172a",
          margin: 0,
          padding: "1rem 1.25rem",
          overflowX: "auto",
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: "0.875rem",
          lineHeight: "1.65",
          color: "#e2e8f0",
        }}
        dangerouslySetInnerHTML={{ __html: highlighted }}
      />
    </div>
  );
}
