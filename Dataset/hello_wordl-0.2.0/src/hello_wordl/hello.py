"""Main functionality for the hello-wordl package."""

def hello(name=None):
    """Return a greeting message.
    
    Args:
        name (str, optional): The name to greet. Defaults to None.
        
    Returns:
        str: A greeting message.
    """
    if name:
        return f"Hello, {name}! Welcome to the wordl!"
    return "Hello, wordl!"
