"""Small reviewed vocabulary; never infer a person's culture or identity."""
OCCUPATIONS = {'construction worker': 'construction', 'construction laborer': 'construction',
               'software engineer': 'software development', 'software developer': 'software development'}
SKILLS = {'book keeping': 'bookkeeping', 'web design and development': 'web development'}

def occupation(value):
    value = value.strip().lower()
    return OCCUPATIONS.get(value, value)

def skills(values):
    return {SKILLS.get(v, v) for v in values}
