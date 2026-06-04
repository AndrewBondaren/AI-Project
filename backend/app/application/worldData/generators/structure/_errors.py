class UnsupportedShapeError(ValueError):
    """shape_type из шаблона не реализован в текущей версии генератора."""


class GenerationError(RuntimeError):
    """Невозможно разместить обязательную комнату или выполнить иное требование шаблона."""
