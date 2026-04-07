"""Auth parser module for extracting information from auth config files."""

import ast
import re
from ..constants import AUTH_CONFIG_PATH


def parse_auth_config():
    """Parse auth config file using Python's AST module.

    Returns:
        dict: Dictionary of auth config classes and their information
    """
    with open(AUTH_CONFIG_PATH, "r") as f:
        content = f.read()

    # Parse the Python file
    try:
        tree = ast.parse(content)
    except SyntaxError:
        print("  Warning: Could not parse auth config file due to syntax error")
        return {}

    # Find all class definitions and their inheritance
    auth_configs = {}

    # First pass: collect all classes
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_name = node.name

            # Check if this is an auth config class
            parent_classes = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    parent_classes.append(base.id)

            # Skip if not auth-related
            if not (
                any("AuthConfig" in parent for parent in parent_classes)
                or "AuthConfig" in class_name
            ):
                continue

            # Get docstring
            docstring = ast.get_docstring(node) or "No description available."

            # Get fields
            fields = []
            for item in node.body:
                # Look for attribute assignments with Field() constructor
                if isinstance(item, ast.AnnAssign) and hasattr(item, "target"):
                    field_name = item.target.id if isinstance(item.target, ast.Name) else None

                    if field_name:
                        # Get field type
                        field_type = None
                        if hasattr(item, "annotation"):
                            if hasattr(ast, "unparse"):  # Python 3.9+
                                field_type = ast.unparse(item.annotation)
                            else:
                                # Fallback for older Python versions
                                if isinstance(item.annotation, ast.Name):
                                    field_type = item.annotation.id
                                elif isinstance(item.annotation, ast.Subscript):
                                    if isinstance(item.annotation.value, ast.Name):
                                        field_type = item.annotation.value.id

                        field_type = field_type or "Unknown"
                        description = "No description"
                        is_required = True
                        default_value = None

                        # Extract Field parameters by traversing the AST
                        if hasattr(item, "value") and isinstance(item.value, ast.Call):
                            for keyword in item.value.keywords:
                                if keyword.arg == "description":
                                    # Simple string
                                    if isinstance(keyword.value, ast.Str):
                                        description = keyword.value.s
                                    # String in Python 3.8+ (ast.Constant)
                                    elif isinstance(keyword.value, ast.Constant) and isinstance(
                                        keyword.value.value, str
                                    ):
                                        description = keyword.value.value
                                    # Concatenated strings or multiline description
                                    elif isinstance(keyword.value, ast.BinOp) or isinstance(
                                        keyword.value, ast.Tuple
                                    ):
                                        # We need the original source for this part
                                        try:
                                            lines = content.split("\n")
                                            lineno = (
                                                keyword.value.lineno - 1
                                            )  # Convert to 0-indexed

                                            # Heuristic: take the current line and the next 3 lines
                                            # to capture multiline descriptions
                                            desc_lines = lines[lineno : lineno + 4]

                                            # Extract the part inside the quotes or parentheses
                                            desc_text = " ".join(desc_lines)
                                            desc_match = re.search(
                                                r'description\s*=\s*(?:\(?\s*"([^"]*)"|\(?\s*\'([^\']*)\')',
                                                desc_text,
                                            )
                                            if desc_match:
                                                description = desc_match.group(
                                                    1
                                                ) or desc_match.group(2)
                                        except Exception as e:
                                            print(f"  Warning: Error extracting description: {e}")

                                elif keyword.arg == "default":
                                    is_required = False
                                    # Extract default value
                                    if isinstance(keyword.value, ast.Str):
                                        default_value = keyword.value.s
                                    elif isinstance(keyword.value, ast.Constant):
                                        default_value = keyword.value.value
                                    elif isinstance(
                                        keyword.value, (ast.Num, ast.Bytes, ast.NameConstant)
                                    ):
                                        # For Python 3.7 and earlier
                                        if isinstance(keyword.value, ast.Num):
                                            default_value = keyword.value.n
                                        elif isinstance(keyword.value, ast.Bytes):
                                            default_value = keyword.value.s
                                        elif isinstance(keyword.value, ast.NameConstant):
                                            default_value = keyword.value.value
                                    elif isinstance(keyword.value, ast.Name):
                                        # For constants like True, False, None
                                        default_value = keyword.value.id
                                    elif isinstance(keyword.value, ast.List):
                                        default_value = "[]"  # Simplified for lists
                                    elif isinstance(keyword.value, ast.Dict):
                                        default_value = "{}"  # Simplified for dicts
                                    elif isinstance(keyword.value, ast.Call):
                                        if hasattr(keyword.value, "func") and hasattr(
                                            keyword.value.func, "id"
                                        ):
                                            # For function calls like list(), dict(), etc.
                                            default_value = f"{keyword.value.func.id}()"
                                        else:
                                            default_value = "custom value"

                        fields.append(
                            {
                                "name": field_name,
                                "type": field_type,
                                "description": description,
                                "required": is_required,
                                "default": default_value,
                            }
                        )

            auth_configs[class_name] = {
                "name": class_name,
                "parent_class": parent_classes[0] if parent_classes else None,
                "docstring": docstring,
                "fields": fields,
            }

    # Second pass: handle inheritance
    for class_name, config in auth_configs.items():
        parent_class = config.get("parent_class")
        if (
            parent_class in auth_configs
            and parent_class != "AuthConfig"
            and parent_class != "BaseConfig"
        ):
            parent_fields = auth_configs[parent_class]["fields"]
            existing_field_names = [field["name"] for field in config["fields"]]

            # Extract the database type from the class name
            db_type = None
            if "AuthConfig" in class_name:
                db_type = class_name.replace("AuthConfig", "")

            for parent_field in parent_fields:
                if parent_field["name"] not in existing_field_names:
                    field_copy = parent_field.copy()

                    # Replace database type in description if needed
                    if db_type and "PostgreSQL" in field_copy["description"]:
                        field_copy["description"] = field_copy["description"].replace(
                            "PostgreSQL", db_type
                        )

                    config["fields"].append(field_copy)

    # Special case for BaseDatabaseAuthConfig
    # Ensure we fully extract the "tables" field which has a complex description in parentheses
    if "BaseDatabaseAuthConfig" in auth_configs:
        tables_pattern = r'tables:\s*str\s*=\s*Field\(\s*default="[^"]*",\s*title="[^"]*",\s*description=\(\s*"([^"]*)"\s*(?:"([^"]*)")?\s*\),?\s*\)'
        tables_match = re.search(tables_pattern, content, re.DOTALL)

        if tables_match:
            description = tables_match.group(1)
            if tables_match.group(2):  # Second part of the description if split
                description += " " + tables_match.group(2)

            # Find tables field and update its description
            for field in auth_configs["BaseDatabaseAuthConfig"]["fields"]:
                if field["name"] == "tables":
                    field["description"] = description
                    break
            # If not found, add it
            else:
                # Try to extract default value for tables field
                default_pattern = r'tables:\s*str\s*=\s*Field\(\s*default="([^"]*)"'
                default_match = re.search(default_pattern, content)
                default_value = default_match.group(1) if default_match else None

                auth_configs["BaseDatabaseAuthConfig"]["fields"].append(
                    {
                        "name": "tables",
                        "type": "str",
                        "description": description,
                        "required": False,  # Has default value
                        "default": default_value,
                    }
                )

            # Also propagate to children
            for class_name, config in auth_configs.items():
                if config.get("parent_class") == "BaseDatabaseAuthConfig":
                    tables_found = False
                    for field in config["fields"]:
                        if field["name"] == "tables":
                            tables_found = True
                            break

                    if not tables_found:
                        db_type = class_name.replace("AuthConfig", "")
                        tables_desc = (
                            description.replace("PostgreSQL", db_type) if db_type else description
                        )

                        # Use the same default value from BaseDatabaseAuthConfig
                        table_default = None
                        for field in auth_configs["BaseDatabaseAuthConfig"]["fields"]:
                            if field["name"] == "tables" and "default" in field:
                                table_default = field["default"]
                                break

                        config["fields"].append(
                            {
                                "name": "tables",
                                "type": "str",
                                "description": tables_desc,
                                "required": False,
                                "default": table_default,
                            }
                        )

    print(f"  Parsed {len(auth_configs)} auth configurations")
    return auth_configs
