from pathlib import Path

root = Path(r"C:\Users\moham\Desktop\Facture_Creature")
models = root / "models.py"
s = models.read_text(encoding="utf-8")
s = s.replace('APP_NAME = "ModernStock Invoice Git Pro"', 'APP_NAME = "Facture_Creature (FC)"')
start = s.index('def default_document() -> InvoiceDocument:')
s = s[:start] + 'def default_document() -> InvoiceDocument:\n    """Return a blank invoice with no sample data."""\n    return InvoiceDocument(versions_text="", sections=[])\n'
models.write_text(s, encoding="utf-8")

main = root / "main.py"
s = main.read_text(encoding="utf-8")
s = s.replace('selectmode="browse")', 'selectmode="extended")', 1)
s = s.replace('("Associer à la ligne", self.assign_selected_commit),', '("Associer à la ligne", self.assign_selected_commit),\n            ("Ajouter les commits sélectionnés", self.create_items_from_selected_commits),')
marker = '    def _selected_commit(self) -> GitCommit | None:\n'
insert = '''    def _selected_commits(self) -> list[GitCommit]:\n        selection = self.commits_tree.selection() if hasattr(self, "commits_tree") else ()\n        return [self.git_commits_by_hash[iid] for iid in selection if iid in self.git_commits_by_hash]\n\n    def create_items_from_selected_commits(self) -> None:\n        commits = self._selected_commits()\n        section_index = self._selected_section_index()\n        if not commits:\n            messagebox.showwarning("Git", "Sélectionnez un ou plusieurs commits.")\n            return\n        if section_index is None:\n            self.document.sections.append(InvoiceSection(title="NOUVELLE SECTION"))\n            section_index = len(self.document.sections) - 1\n        section = self.document.sections[section_index]\n        existing = {item.git_commit for item in section.items if item.git_commit}\n        for commit in commits:\n            if commit.full_hash in existing:\n                continue\n            item = InvoiceItem(description=commit.subject, amount=Decimal("0"), price_label="GRATUIT")\n            item.apply_git_commit(commit, version_fallback=version_from_section(section.title))\n            section.items.append(item)\n            existing.add(commit.full_hash)\n        self._mark_dirty()\n        self._refresh_sections(section_index)\n        self._refresh_items(len(section.items) - 1 if section.items else None)\n        self.notebook.select(self.content_tab)\n        self.status_var.set(f"{len(commits)} commit(s) ajouté(s) à la section")\n\n'''
s = s.replace(marker, insert + marker)
s = s.replace('self._refresh_sections(0)', 'self._refresh_sections(0 if self.document.sections else None)')
s = s.replace('self._load_document(default_document())\n            self.status_var.set("Nouvelle facture")', 'self._load_document(default_document())\n            self.status_var.set("Nouvelle facture vide")')
main.write_text(s, encoding="utf-8")
