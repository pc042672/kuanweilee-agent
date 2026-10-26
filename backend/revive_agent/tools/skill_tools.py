"""Skill loader tools — dynamic guidelines and templates."""

from pathlib import Path
from typing import Dict, Any, Optional


def _parse_skill_file(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse a skill markdown file with YAML front matter.

    Returns:
        Dictionary with skill metadata (name, description, license) or None if invalid.
    """
    try:
        content = file_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return None

        end_idx = content.find("---", 3)
        if end_idx == -1:
            return None

        front_matter = content[3:end_idx].strip()

        skill_info = {}
        for line in front_matter.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                skill_info[key.strip()] = value.strip()

        if "name" not in skill_info:
            return None

        return skill_info
    except Exception:
        return None


# Resolve skills directory once
_SKILLS_DIR = Path(__file__).resolve().parent.parent.parent / "skills"


def _find_skill_file(skill_name: str) -> Optional[tuple[Path, Dict[str, Any]]]:
    """Find a skill file by name, returning (path, parsed_info) to avoid re-parsing."""
    for skill_file in _SKILLS_DIR.glob("**/*.md"):
        skill_info = _parse_skill_file(skill_file)
        if skill_info and skill_info.get("name") == skill_name:
            return skill_file, skill_info
    return None


def list_skills_tool() -> Dict[str, Any]:
    """
    List all available skills in the skills directory.
    Skills provide templates, guidelines, and best practices for specific tasks.

    Returns:
        A dictionary with skill names, descriptions, and available templates.
    """
    try:
        if not _SKILLS_DIR.exists():
            return {"success": False, "error": "Skills directory not found"}

        skills = []

        for skill_file in _SKILLS_DIR.glob("**/SKILL.md"):
            skill_info = _parse_skill_file(skill_file)
            if skill_info:
                templates_dir = skill_file.parent / "templates"
                templates = []
                if templates_dir.exists():
                    templates = [f.name for f in templates_dir.iterdir() if f.is_file()]

                skill_info["templates"] = templates
                skill_info["path"] = str(skill_file.relative_to(_SKILLS_DIR.parent))
                skills.append(skill_info)

        for md_file in _SKILLS_DIR.glob("*.md"):
            if md_file.name != "SKILL.md":
                skill_info = _parse_skill_file(md_file)
                if skill_info:
                    skill_info["path"] = str(md_file.relative_to(_SKILLS_DIR.parent))
                    skills.append(skill_info)

        return {
            "success": True,
            "count": len(skills),
            "skills": skills
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to list skills: {e}"}


def get_skill_tool(skill_name: str) -> Dict[str, Any]:
    """
    Load a specific skill by name.
    Returns the full skill content including guidelines, templates, and best practices.

    Args:
        skill_name: The name of the skill to load (e.g., 'brand-guidelines')

    Returns:
        A dictionary with skill metadata and full content.
    """
    try:
        found = _find_skill_file(skill_name)
        if found is None:
            return {"success": False, "error": f"Skill '{skill_name}' not found"}

        skill_file, skill_info = found
        content = skill_file.read_text(encoding="utf-8")

        templates = {}
        templates_dir = skill_file.parent / "templates"
        if templates_dir.exists():
            for template_file in templates_dir.iterdir():
                if template_file.is_file():
                    templates[template_file.name] = template_file.read_text(encoding="utf-8")

        return {
            "success": True,
            "skill": {
                **skill_info,
                "content": content,
                "templates": templates,
                "path": str(skill_file.relative_to(_SKILLS_DIR.parent))
            }
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to load skill: {e}"}


def get_skill_template_tool(skill_name: str, template_name: str) -> Dict[str, Any]:
    """
    Load a specific template from a skill.

    Args:
        skill_name: The name of the skill (e.g., 'brand-guidelines')
        template_name: The name of the template file (e.g., 'generator_template.js')

    Returns:
        A dictionary with the template content.
    """
    try:
        found = _find_skill_file(skill_name)
        if found is None:
            return {"success": False, "error": f"Skill '{skill_name}' not found"}

        skill_file, _ = found
        templates_dir = skill_file.parent / "templates"
        template_path = templates_dir / template_name

        if template_path.exists():
            content = template_path.read_text(encoding="utf-8")
            return {
                "success": True,
                "skill_name": skill_name,
                "template_name": template_name,
                "content": content
            }
        return {"success": False, "error": f"Template '{template_name}' not found in skill '{skill_name}'"}
    except Exception as e:
        return {"success": False, "error": f"Failed to load template: {e}"}
