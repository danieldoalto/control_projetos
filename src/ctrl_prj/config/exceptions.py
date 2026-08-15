"""Exceções específicas do módulo de configuração."""


class ConfigError(Exception):
    """Exceção base para erros de configuração."""
    pass


class ConfigNotFoundError(ConfigError):
    """Lançada quando o arquivo de configuração especificado não é encontrado."""
    pass


class ConfigParseError(ConfigError):
    """Lançada quando o arquivo YAML de configuração possui sintaxe inválida."""
    pass


class ConfigValidationError(ConfigError):
    """Lançada quando os dados de configuração falham na validação de tipos ou estrutura."""
    pass
