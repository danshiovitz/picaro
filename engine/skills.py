#!/usr/bin/python3

DUELING = "Dueling"
FORMATION_FIGHTING = "Formation Fighting"
BRUTAL_FIGHTING = "Brutal Fighting"
SHOOT = "Shoot"
THROW = "Throw"
RIDE = "Ride"
    
RESEARCH = "Research"
DEBATE = "Debate"
CHARM = "Charm"
CAROUSING = "Carousing"
COMMAND = "Command"
ENDURANCE = "Endurance"

THAUMATURGY = "Thaumaturgy"
SPIRIT_BINDING = "Spirit Binding"
MESMERISM = "Mesmerism"
STEALTH = "Stealth"
ANIMAL_TRAINING = "Animal Training"
CLIMB = "Climb"

DESERT_LORE = "Desert Lore"
FOREST_LORE = "Forest Lore"
SEA_LORE = "Sea Lore"
MOUNTAIN_LORE = "Mountain Lore"
JUNGLE_LORE = "Jungle Lore"
PLAINS_LORE = "Plains Lore"

MECHANISMS = "Mechanisms"
MIGHT = "Might"
OBSERVATION = "Observation"
ACROBATICS = "Acrobatics"
APPRAISAL = "Appraisal"
SPEED = "Speed"

PICKPOCKET = "Pickpocket"
DOCTOR = "Doctor"
ARCHITECTURE = "Architecture"
NAVIGATION = "Navigation"
SKILL_X = "Skill X"
SKILL_Y = "Skill Y"
        
SKILLS = set(v for k,v in globals().items() if not k.startswith("__"))
