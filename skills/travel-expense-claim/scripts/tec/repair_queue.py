"""Operational repair queue: one item per missing fact or return reason.

Organization (choice 4): items are grouped by responsible person, then by
subject. History is an append-only event list; item state is derived from it.
A batch that satisfies some, but not all, open items of one owner+subject group
is recorded as a partial response; the unsatisfied items stay open unchanged.
Drafts are written locally and never sent.
"""


from . import routing


def _cap(text):
    return text[:1].upper() + text[1:]


def item_id(record_id):
    return "RQ-" + record_id[len("ISS-"):] if record_id.startswith("ISS-") else "RQ-" + record_id


class RepairQueue:
    def __init__(self, run_id):
        self.run_id = run_id
        self.items = {}    # item_id -> current item
        self.events = []   # append-only

    def _event(self, batch, kind, item, **extra):
        ev = {"seq": len(self.events) + 1, "run_id": self.run_id, "batch_id": "batch-%d" % batch, "event": kind,
              "item_id": item["item_id"] if item else None, **extra}
        self.events.append(ev)
        return ev

    def update(self, batch, issues, current_revisions, inputs_by_subject):
        """Apply this batch's open issues. Returns the events appended for the batch."""
        start = len(self.events)
        ref = {"run_id": self.run_id, "batch_id": "batch-%d" % batch}
        now = {item_id(i["record_id"]): i for i in issues}
        open_before = {k: v for k, v in self.items.items() if v["status"] == "open"}

        for iid, i in sorted(now.items()):
            fields = {"subject_type": i["subject_type"], "subject_id": i["subject_id"], "revision": i["revision"],
                      "trip_id": i["trip_id"], "trip_revision": i["trip_revision"], "permit_id": i["permit_id"],
                      "permit_revision": i["permit_revision"], "cost_id": i["cost_id"], "fact_code": i["fact_code"],
                      "missing_fact": i["reason"], "owner": i["owner"], "next_action": i["resolution_needed"],
                      "decision_authority": i.get("decision_authority", i["owner"]), "follow_up": i.get("follow_up"),
                      "route_basis": i.get("route_basis"), "hold_impact": i.get("hold_impact"),
                      "source_ids": i["source_ids"], "issue_record_id": i["record_id"]}
            cur = self.items.get(iid)
            twin = next((v for k, v in self.items.items() if k != iid and v["status"] == "open"
                         and (v["subject_id"], v["revision"], v["cost_id"], routing.label(v["fact_code"]), v["owner"]) ==
                         (i["subject_id"], i["revision"], i["cost_id"], routing.label(i["fact_code"]), i["owner"])), None)
            if cur is None and twin:
                # A second request for the same fact keeps the original finding and owner; the original item is
                # updated with the new source and next action instead of creating a new request (INT5 01:51).
                if i["record_id"] not in twin.setdefault("also_covers", []):
                    twin["also_covers"].append(i["record_id"])
                    twin["source_ids"] = sorted(set(twin["source_ids"]) | set(i["source_ids"]))
                    twin["next_action"] = i["resolution_needed"]
                    twin["last_changed"] = dict(ref)
                    self._event(batch, "merged-into-existing", twin, subject=i["subject_id"], fact=i["fact_code"],
                                merged_record=i["record_id"], source_ids=i["source_ids"], next_action=twin["next_action"])
                continue
            if cur is None:
                prior = self._replaced(i)
                item = dict(fields, item_id=iid, status="open", opened=dict(ref), last_changed=dict(ref),
                            supersedes=prior["item_id"] if prior else None, superseded_by=None)
                if prior:
                    prior["superseded_by"] = iid
                self.items[iid] = item
                self._event(batch, "opened", item, owner=item["owner"], subject=i["subject_id"], revision=i["revision"],
                            fact=i["fact_code"], cost_id=i["cost_id"], supersedes=item["supersedes"],
                            source_ids=i["source_ids"], next_action=item["next_action"])
            elif cur["status"] != "open":
                cur.update(fields, status="open", last_changed=dict(ref))
                self._event(batch, "reopened", cur, owner=cur["owner"], subject=i["subject_id"], fact=i["fact_code"],
                            reason=i["reason"])
            else:
                changed = {k: fields[k] for k in ("owner", "next_action", "missing_fact", "follow_up", "hold_impact")
                           if cur.get(k) != fields[k]}
                if changed:
                    cur.update(fields, last_changed=dict(ref))
                    self._event(batch, "updated", cur, changes=changed)

        closed_by_group = {}
        for iid, item in sorted(open_before.items()):
            if iid in now:
                continue
            subj_rev = current_revisions.get((item["subject_type"], item["subject_id"]))
            if item["revision"] is not None and subj_rev is not None and subj_rev > item["revision"]:
                kind = "superseded"
            else:
                kind = "satisfied"
            # Prefer evidence for this exact cost; fall back to the subject's inputs this batch.
            evidence = inputs_by_subject.get((item["subject_id"], item["cost_id"])) or \
                inputs_by_subject.get(item["subject_id"], [])
            # The item itself records its new status and the source that closed it (INT5 01:51).
            item.update(status=kind, last_changed=dict(ref), resolved_by=sorted(set(evidence)))
            self._event(batch, kind, item, owner=item["owner"], subject=item["subject_id"], fact=item["fact_code"],
                        evidence=evidence, superseded_by=item.get("superseded_by"))
            closed_by_group.setdefault((item["owner"], item["subject_id"], item["revision"]), []).append(iid)

        for (owner, subj, rev), closed in sorted(closed_by_group.items(), key=lambda x: str(x[0])):
            remaining = sorted(k for k, v in self.items.items() if v["status"] == "open" and v["owner"] == owner
                               and v["subject_id"] == subj and v["revision"] == rev)
            if remaining:
                self._event(batch, "partial-response", None, owner=owner, subject=subj, revision=rev,
                            satisfied=sorted(closed), still_open=remaining)
        return self.events[start:]

    def _replaced(self, i):
        """Link a new-revision item to the same open fact on an earlier revision of the subject."""
        for it in self.items.values():
            if (it["subject_type"], it["subject_id"], it["fact_code"], it["cost_id"]) == (
                    i["subject_type"], i["subject_id"], i["fact_code"], i["cost_id"]) and it["revision"] is not None \
                    and i["revision"] is not None and it["revision"] < i["revision"] and it["superseded_by"] is None:
                return it
        return None

    def open_items(self):
        return sorted([v for v in self.items.values() if v["status"] == "open"],
                      key=lambda v: (v["owner"] or "", _nat(v["subject_id"]), v["item_id"]))

    def drafts(self):
        """{owner: markdown} request drafts, one per responsible person. Never sent."""
        by = {}
        for it in self.open_items():
            by.setdefault(it["owner"], []).append(it)
        out = {}
        for owner, items in by.items():
            follow = sorted({it["follow_up"] for it in items if it.get("follow_up")})
            lines = ["# DRAFT request to %s — not sent" % owner, "",
                     "Prepared locally by the travel-expense-claim Skill (run `%s`). A person must review and send it; "
                     "the Skill never sends requests." % self.run_id, "",
                     "%s is asked as the party who supplies each fact or decision below. Follow-up on missing replies: "
                     "%s (Travel Administration Lead)." % (owner, ", ".join(follow) or "Travel Administration Lead"), ""]
            subj = None
            for it in items:
                key = (it["subject_type"], it["subject_id"], it["revision"])
                if key != subj:
                    subj = key
                    rev = " revision %s" % it["revision"] if it["revision"] is not None else ""
                    tr = " (trip %s r%s%s)" % (it["trip_id"], it["trip_revision"],
                                               ", permit %s r%s" % (it["permit_id"], it["permit_revision"]) if it["permit_id"] else "")
                    lines += (["## %s %s%s%s" % (it["subject_type"], it["subject_id"], rev, tr), ""] if lines[-1] == "" else
                              ["", "## %s %s%s%s" % (it["subject_type"], it["subject_id"], rev, tr), ""])
                lines.append("- **%s**%s. %s. Next action: %s. Evidence: %s. Reference `%s`, opened %s / %s." % (
                    routing.label(it["fact_code"]), " (cost %s)" % it["cost_id"] if it["cost_id"] else "",
                    _cap(routing.sentence(it["missing_fact"])), routing.sentence(it["next_action"]),
                    ", ".join(it["source_ids"]), it["item_id"], it["opened"]["run_id"], it["opened"]["batch_id"]))
                if it.get("hold_impact"):
                    lines.append("  While this is open: %s" % it["hold_impact"])
            out[owner] = "\n".join(lines) + "\n"
        return out


def _nat(s):
    import re
    return [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s or "")]
