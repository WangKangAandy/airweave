"""Main entry point for the connector documentation generator."""

import os

from .constants import DOCS_CONNECTORS_DIR
from .generators.mdx_generator import generate_mdx_content
from .parsers.auth_parser import parse_auth_config
from .parsers.config_parser import parse_config_file
from .parsers.entity_parser import parse_entity_file
from .parsers.source_parser import parse_source_file
from .utils.file_utils import (
    copy_svg_icon,
    get_connectors_from_sources,  # Updated to use source-based discovery
    update_docs_yml,
    update_or_create_mdx,
)


def main():
    """Generate documentation for connectors."""
    print("Starting connector documentation generation...")

    # Get list of connectors from source files (improved approach)
    connectors = get_connectors_from_sources()
    print(f"Found {len(connectors)} connectors from source files")

    # Parse auth and config files
    auth_configs = parse_auth_config()
    config_configs = parse_config_file()

    # Process each connector
    valid_connectors = []

    for connector_name in sorted(connectors):
        print(f"Processing connector: {connector_name}")

        # Parse entity and source files
        entity_info = parse_entity_file(connector_name)
        source_info = parse_source_file(connector_name)

        # Skip if no entity or source info is available
        if not entity_info and not source_info:
            print(
                f"  Skipping {connector_name} - no entity or source information found"
            )
            continue

        valid_connectors.append(connector_name)

        # Generate MDX content with both auth and config information
        mdx_content = generate_mdx_content(
            connector_name, entity_info, source_info, auth_configs, config_configs
        )

        # Create connector docs directory and files
        connector_docs_dir = DOCS_CONNECTORS_DIR / connector_name

        # Create the directory if it doesn't exist
        os.makedirs(connector_docs_dir, exist_ok=True)

        # Copy SVG icon to connector directory (optional - won't fail if missing)
        copy_svg_icon(connector_name, connector_docs_dir)

        # Create or update main.mdx
        update_or_create_mdx(connector_name, connector_docs_dir, mdx_content)

    # Update the docs.yml file with the valid connectors
    update_docs_yml(valid_connectors)

    print(f"Generated documentation for {len(valid_connectors)} connectors")
    print("Connector documentation generation complete!")


if __name__ == "__main__":
    main()
