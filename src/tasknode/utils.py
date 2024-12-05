def format_time(seconds: int) -> str:
    """
    Format seconds into HH:MM:SS string.
    
    Args:
        seconds: Number of seconds to format
        
    Returns:
        String in format "HH:MM:SS"
    """
    if seconds is None:
        return "N/A"
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def format_file_size(bytes: int, unit: str = None) -> str:
    """
    Format bytes into a human-readable size string.
    
    Args:
        bytes: Number of bytes to format
        unit: Optional target unit (B, KB, MB, GB, TB). If None, best unit is chosen.
        
    Returns:
        String with appropriate unit (B, KB, MB, GB or TB)
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    
    def convert(bytes: int, unit_idx: int = 0) -> tuple[float, str]:
        if unit_idx >= len(units) or bytes < 1024 or (unit and units[unit_idx] == unit):
            return bytes, units[unit_idx]
        return convert(bytes / 1024, unit_idx + 1)
    
    value, chosen_unit = convert(bytes, 0)
    return f"{value:.2f} {chosen_unit}"
