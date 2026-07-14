import { useRef, useState } from "react";
import type { Education, Project, Resume, Role, Section, SectionType, SkillGroup } from "../../types";
import { Area, Bullets, EntryList, Field } from "./fields";

const emptyRole = (): Role => ({ title: "", organization: "", location: "", start_date: "", end_date: "", bullets: [] });
const emptyProject = (): Project => ({ name: "", stack: "", bullets: [] });
const emptyEducation = (): Education => ({ school: "", location: "", gpa: "", start_date: "", end_date: "", coursework: "" });

const TYPE_MENU: { type: SectionType; label: string; hint: string; title: string }[] = [
  { type: "roles", label: "Roles", hint: "dated entries + bullets", title: "Experience" },
  { type: "text", label: "Text", hint: "a paragraph", title: "Summary" },
  { type: "bullets", label: "Bullets", hint: "simple list", title: "Certifications" },
  { type: "projects", label: "Projects", hint: "name + stack + bullets", title: "Projects" },
  { type: "skills", label: "Skills", hint: "category groups", title: "Technical Skills" },
  { type: "education", label: "Education", hint: "schools", title: "Education" },
];

function blankSection(type: SectionType, title: string): Section {
  switch (type) {
    case "text": return { type, title, text: "" };
    case "roles": return { type, title, entries: [] };
    case "projects": return { type, title, entries: [] };
    case "skills": return { type, title, groups: [] };
    case "education": return { type, title, entries: [] };
    case "bullets": return { type, title, items: [] };
  }
}

function roleBody(r: Role, update: (p: Partial<Role>) => void) {
  return (
    <>
      <div className="frow">
        <Field label="Title" value={r.title} onChange={(v) => update({ title: v })} />
        <Field label="Organization" value={r.organization} onChange={(v) => update({ organization: v })} />
      </div>
      <div className="frow">
        <Field label="Location" value={r.location} onChange={(v) => update({ location: v })} />
        <Field label="Start" value={r.start_date} onChange={(v) => update({ start_date: v })} />
        <Field label="End" value={r.end_date} onChange={(v) => update({ end_date: v })} />
      </div>
      <span className="ef-k">Bullets</span>
      <Bullets items={r.bullets ?? []} onChange={(b) => update({ bullets: b })} />
    </>
  );
}

function SkillGroups({ groups, onChange }: { groups: SkillGroup[]; onChange: (g: SkillGroup[]) => void }) {
  const update = (i: number, patch: Partial<SkillGroup>) => {
    const next = [...groups];
    next[i] = { ...next[i], ...patch };
    onChange(next);
  };
  return (
    <div>
      {groups.map((g, i) => (
        <div className="frow" key={i} style={{ marginBottom: 6 }}>
          <Field label="Category" value={g.category} onChange={(v) => update(i, { category: v })} />
          <Field label="Items (comma-separated)" value={g.items} onChange={(v) => update(i, { items: v })} />
          <button className="mini" title="remove" style={{ alignSelf: "flex-end", marginBottom: 8 }} onClick={() => onChange(groups.filter((_, j) => j !== i))}>✕</button>
        </div>
      ))}
      <button className="mini add" onClick={() => onChange([...groups, { category: "", items: "" }])}>+ group</button>
    </div>
  );
}

function SectionBody({ sec, update }: { sec: Section; update: (patch: Partial<Section>) => void }) {
  switch (sec.type) {
    case "text":
      return <Area label="" value={sec.text} onChange={(v) => update({ text: v })} rows={4} />;
    case "roles":
      return <EntryList items={(sec.entries ?? []) as Role[]} onChange={(x) => update({ entries: x })} empty={emptyRole} addLabel="entry" render={roleBody} />;
    case "projects":
      return (
        <EntryList
          items={(sec.entries ?? []) as Project[]}
          onChange={(x) => update({ entries: x })}
          empty={emptyProject}
          addLabel="project"
          render={(p, u) => (
            <>
              <div className="frow">
                <Field label="Name" value={p.name} onChange={(v) => u({ name: v })} />
                <Field label="Stack" value={p.stack} onChange={(v) => u({ stack: v })} />
              </div>
              <span className="ef-k">Bullets</span>
              <Bullets items={p.bullets ?? []} onChange={(b) => u({ bullets: b })} />
            </>
          )}
        />
      );
    case "skills":
      return <SkillGroups groups={sec.groups ?? []} onChange={(g) => update({ groups: g })} />;
    case "education":
      return (
        <EntryList
          items={(sec.entries ?? []) as Education[]}
          onChange={(x) => update({ entries: x })}
          empty={emptyEducation}
          addLabel="school"
          render={(ed, u) => (
            <>
              <div className="frow">
                <Field label="School" value={ed.school} onChange={(v) => u({ school: v })} />
                <Field label="Location" value={ed.location} onChange={(v) => u({ location: v })} />
              </div>
              <div className="frow">
                <Field label="GPA" value={ed.gpa} onChange={(v) => u({ gpa: v })} />
                <Field label="Start" value={ed.start_date} onChange={(v) => u({ start_date: v })} />
                <Field label="End" value={ed.end_date} onChange={(v) => u({ end_date: v })} />
              </div>
              <Field label="Coursework" value={ed.coursework} onChange={(v) => u({ coursework: v })} />
            </>
          )}
        />
      );
    case "bullets":
      return <Bullets items={sec.items ?? []} onChange={(it) => update({ items: it })} />;
  }
}

export function SectionEditor({ value, onChange }: { value: Resume; onChange: (r: Resume) => void }) {
  const personal = value.personal ?? {};
  const sections = value.sections ?? [];
  const [adding, setAdding] = useState(false);
  const from = useRef<number | null>(null);

  const setP = (patch: Partial<Resume["personal"]>) => onChange({ ...value, personal: { ...personal, ...patch } });
  const setSections = (s: Section[]) => onChange({ ...value, sections: s });
  const update = (i: number, patch: Partial<Section>) => {
    const next = [...sections];
    next[i] = { ...next[i], ...patch };
    setSections(next);
  };
  const move = (i: number, to: number) => {
    if (to < 0 || to >= sections.length) return;
    const next = [...sections];
    const [x] = next.splice(i, 1);
    next.splice(to, 0, x);
    setSections(next);
  };

  return (
    <div className="editor">
      <section className="ed-section">
        <h3 className="ed-h">Personal</h3>
        <Field label="Name" value={personal.name} onChange={(v) => setP({ name: v })} />
        <div className="frow">
          <Field label="Email" value={personal.email} onChange={(v) => setP({ email: v })} />
          <Field label="Phone" value={personal.phone} onChange={(v) => setP({ phone: v })} />
        </div>
        <div className="frow">
          <Field label="GitHub" value={personal.github} onChange={(v) => setP({ github: v })} />
          <Field label="LinkedIn" value={personal.linkedin} onChange={(v) => setP({ linkedin: v })} />
        </div>
      </section>

      {sections.map((sec, i) => (
        <section
          className="sec-card"
          key={i}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => { if (from.current != null) move(from.current, i); from.current = null; }}
        >
          <div className="sec-head">
            <span className="grip" draggable onDragStart={() => (from.current = i)} title="drag to reorder">⠿</span>
            <input className="sec-title" value={sec.title} onChange={(e) => update(i, { title: e.target.value })} />
            <span className="type-badge">{sec.type}</span>
            <button className="mini" title="move up" onClick={() => move(i, i - 1)}>▲</button>
            <button className="mini" title="move down" onClick={() => move(i, i + 1)}>▼</button>
            <button className="mini" title="remove section" onClick={() => setSections(sections.filter((_, j) => j !== i))}>✕</button>
          </div>
          <SectionBody sec={sec} update={(patch) => update(i, patch)} />
        </section>
      ))}

      {adding ? (
        <div className="add-menu">
          <span className="ef-k">Add a section</span>
          <div className="type-grid">
            {TYPE_MENU.map((t) => (
              <button
                key={t.type}
                className="type-opt"
                onClick={() => { setSections([...sections, blankSection(t.type, t.title)]); setAdding(false); }}
              >
                <strong>{t.label}</strong>
                <span className="muted">{t.hint}</span>
              </button>
            ))}
          </div>
          <button className="mini" onClick={() => setAdding(false)}>cancel</button>
        </div>
      ) : (
        <button className="add-entry" onClick={() => setAdding(true)}>+ Add section</button>
      )}
    </div>
  );
}
