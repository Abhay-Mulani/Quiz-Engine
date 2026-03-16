"""
Adaptive difficulty engine.

Rules:
  - Correct answer  → increment correct_streak, reset incorrect_streak
  - Incorrect answer → increment incorrect_streak, reset correct_streak

  - After CORRECT_STREAK_TO_INCREASE correct answers in a row → increase difficulty
  - After INCORRECT_STREAK_TO_DECREASE wrong answers in a row → decrease difficulty

Difficulty ladder: easy → medium → hard
"""

from app.core.config import settings

DIFFICULTY_LADDER = ["easy", "medium", "hard"]


def _level(d: str) -> int:
    try:
        return DIFFICULTY_LADDER.index(d)
    except ValueError:
        return 0


def update_difficulty(student, is_correct: bool) -> str:
    """
    Update student streak counters and return the new difficulty level.
    Mutates the student object in place (caller must commit).
    """
    if is_correct:
        student.correct_streak += 1
        student.incorrect_streak = 0
        student.total_correct += 1
    else:
        student.incorrect_streak += 1
        student.correct_streak = 0

    student.total_answered += 1

    current_level = _level(student.current_difficulty)

    if (
        is_correct
        and student.correct_streak >= settings.CORRECT_STREAK_TO_INCREASE
        and current_level < len(DIFFICULTY_LADDER) - 1
    ):
        student.current_difficulty = DIFFICULTY_LADDER[current_level + 1]
        student.correct_streak = 0  # reset after promotion

    elif (
        not is_correct
        and student.incorrect_streak >= settings.INCORRECT_STREAK_TO_DECREASE
        and current_level > 0
    ):
        student.current_difficulty = DIFFICULTY_LADDER[current_level - 1]
        student.incorrect_streak = 0  # reset after demotion

    return student.current_difficulty
