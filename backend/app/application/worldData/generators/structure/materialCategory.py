from enum import Enum


class MaterialCategory(str, Enum):
    """
    Базовые категории материалов. Фиксированы в движке.
    Мир может добавлять кастомные через world.material_category_registry.
    """
    CONSTRUCTION = "construction"   # строительные
    METAL        = "metal"          # металлы и сплавы
    CRAFTED      = "crafted"        # из нескольких компонентов
    REFINED      = "refined"        # переработан из одного источника
    RAW          = "raw"            # сырьё
    ORGANIC      = "organic"        # биологическое происхождение
    CONSUMABLE   = "consumable"     # расходники
    MINERAL      = "mineral"        # минералы и камни
    MAGIC        = "magic"          # магические материалы


class MaterialUseType(str, Enum):
    """
    Базовые типы применения материала. Фиксированы в движке.
    Мир может добавлять кастомные через world.material_use_type_registry.
    """
    WALL     = "wall"
    FLOOR    = "floor"
    COLUMN   = "column"
    DOOR     = "door"
    GATE     = "gate"
    RAILING  = "railing"
    CEILING  = "ceiling"   # внутренняя поверхность верха комнаты
    ROOF     = "roof"      # внешнее покрытие здания
    ANY      = "any"
