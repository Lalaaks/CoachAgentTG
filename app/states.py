from aiogram.fsm.state import State, StatesGroup

class StudyFlow(StatesGroup):
    start_topic = State()
    start_goal = State()
    start_planned = State()

    end_done_minutes = State()
    end_what_done = State()
    end_stuck = State()
    end_focus = State()
    end_difficulty = State()
    end_next_step = State()
    end_feynman = State()
