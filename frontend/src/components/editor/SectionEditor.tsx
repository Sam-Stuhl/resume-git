import type { Education, Project, Resume, Role } from "../../types";
import { Area, Bullets, EntryList, Field } from "./fields";

const emptyRole = (): Role => ({ title: "", organization: "", location: "", start_date: "", end_date: "", bullets: [] });
const emptyProject = (): Project => ({ name: "", stack: "", bullets: [] });
const emptyEducation = (): Education => ({ school: "", location: "", gpa: "", start_date: "", end_date: "", coursework: "" });

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="ed-section">
      <h3 className="ed-h">{title}</h3>
      {children}
    </section>
  );
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

function SkillsEditor({ value, onChange }: { value: Record<string, string>; onChange: (s: Record<string, string>) => void }) {
  const entries = Object.entries(value);
  const rename = (i: number, key: string) => {
    const next: Record<string, string> = {};
    entries.forEach(([k, v], j) => (next[j === i ? key : k] = v));
    onChange(next);
  };
  const setVal = (key: string, v: string) => onChange({ ...value, [key]: v });
  const remove = (key: string) => {
    const next = { ...value };
    delete next[key];
    onChange(next);
  };
  return (
    <div>
      {entries.map(([k, v], i) => (
        <div className="entry-card" key={i}>
          <div className="frow">
            <Field label="Category" value={k} onChange={(nk) => rename(i, nk)} />
            <button className="mini" title="remove" style={{ alignSelf: "flex-end", marginBottom: 8 }} onClick={() => remove(k)}>✕</button>
          </div>
          <Field label="Items (comma-separated)" value={v} onChange={(nv) => setVal(k, nv)} />
        </div>
      ))}
      <button className="add-entry" onClick={() => onChange({ ...value, [`Category ${entries.length + 1}`]: "" })}>+ skill group</button>
    </div>
  );
}

export function SectionEditor({ value, onChange }: { value: Resume; onChange: (r: Resume) => void }) {
  const set = (patch: Partial<Resume>) => onChange({ ...value, ...patch });
  const personal = value.personal ?? {};
  const setP = (patch: Partial<Resume["personal"]>) => set({ personal: { ...personal, ...patch } });

  return (
    <div className="editor">
      <Section title="Personal">
        <Field label="Name" value={personal.name} onChange={(v) => setP({ name: v })} />
        <div className="frow">
          <Field label="Email" value={personal.email} onChange={(v) => setP({ email: v })} />
          <Field label="Phone" value={personal.phone} onChange={(v) => setP({ phone: v })} />
        </div>
        <div className="frow">
          <Field label="GitHub" value={personal.github} onChange={(v) => setP({ github: v })} />
          <Field label="LinkedIn" value={personal.linkedin} onChange={(v) => setP({ linkedin: v })} />
        </div>
      </Section>

      <Section title="Summary">
        <Area label="" value={value.summary} onChange={(v) => set({ summary: v })} rows={4} />
      </Section>

      <Section title="Experience">
        <EntryList items={value.experience ?? []} onChange={(x) => set({ experience: x })} empty={emptyRole} addLabel="experience" render={roleBody} />
      </Section>

      <Section title="Projects">
        <EntryList
          items={value.projects ?? []}
          onChange={(x) => set({ projects: x })}
          empty={emptyProject}
          addLabel="project"
          render={(p, update) => (
            <>
              <div className="frow">
                <Field label="Name" value={p.name} onChange={(v) => update({ name: v })} />
                <Field label="Stack" value={p.stack} onChange={(v) => update({ stack: v })} />
              </div>
              <span className="ef-k">Bullets</span>
              <Bullets items={p.bullets ?? []} onChange={(b) => update({ bullets: b })} />
            </>
          )}
        />
      </Section>

      <Section title="Leadership">
        <EntryList items={value.leadership ?? []} onChange={(x) => set({ leadership: x })} empty={emptyRole} addLabel="entry" render={roleBody} />
      </Section>

      <Section title="Skills">
        <SkillsEditor value={value.skills ?? {}} onChange={(s) => set({ skills: s })} />
      </Section>

      <Section title="Education">
        <EntryList
          items={value.education ?? []}
          onChange={(x) => set({ education: x })}
          empty={emptyEducation}
          addLabel="school"
          render={(ed, update) => (
            <>
              <div className="frow">
                <Field label="School" value={ed.school} onChange={(v) => update({ school: v })} />
                <Field label="Location" value={ed.location} onChange={(v) => update({ location: v })} />
              </div>
              <div className="frow">
                <Field label="GPA" value={ed.gpa} onChange={(v) => update({ gpa: v })} />
                <Field label="Start" value={ed.start_date} onChange={(v) => update({ start_date: v })} />
                <Field label="End" value={ed.end_date} onChange={(v) => update({ end_date: v })} />
              </div>
              <Field label="Coursework" value={ed.coursework} onChange={(v) => update({ coursework: v })} />
            </>
          )}
        />
      </Section>
    </div>
  );
}
