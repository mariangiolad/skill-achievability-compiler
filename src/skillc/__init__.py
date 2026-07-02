"""skillc -- the Skill Achievability Compiler.

Decides whether the goal of an agent skill (SKILL.md / agent markdown / a
formal achievability pack) is achievable in a given capability context.
Sound for refutation (Coq-proved core, proof/SkillAchievability.v);
deliberately incomplete for achievement.
"""
from .audit import Finding, audit_bundle, audit_tree
from .checker import Checker, Verdict, check
from .evaluate import evaluate, load_corpus
from .frontend.markdown import CompileResult, compile_file, compile_markdown
from .pack import Capability, Pack, PackError, validate_pack
from .profiles import Profile, builtin_profiles, load_profile
from .session import ProjectionError, parse_local, project, subtype

__version__ = "0.3.0"

__all__ = [
    "Checker", "Verdict", "check",
    "Pack", "Capability", "PackError", "validate_pack",
    "Profile", "load_profile", "builtin_profiles",
    "CompileResult", "compile_markdown", "compile_file",
    "project", "subtype", "parse_local", "ProjectionError",
    "Finding", "audit_bundle", "audit_tree",
    "evaluate", "load_corpus",
    "__version__",
]
