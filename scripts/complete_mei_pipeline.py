#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Complete MEI Pipeline

This script integrates all components of the MEI workflow, from polygon conversion to MEI generation.
"""

import os
import json
import argparse
import xml.etree.ElementTree as ET
import sys
import logging
from typing import Dict, List, Optional, Any, Tuple
import importlib.util
import subprocess
import uuid
import shutil
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mei_pipeline.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("mei_pipeline")

def import_module_from_file(module_name, file_path):
    """Import a module from a file path dynamically."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def ensure_directory(directory):
    """Ensure a directory exists, creating it if necessary."""
    if not os.path.exists(directory):
        os.makedirs(directory)
        logger.info(f"Created directory: {directory}")

def run_polygons_to_jsomr(polygon_file, output_jsomr, vertical_tolerance=100):
    """
    Convert polygon data to JSOMR format.
    
    Args:
        polygon_file: Path to polygon data file
        output_jsomr: Path to save the JSOMR output
        vertical_tolerance: Tolerance for grouping staves vertically
    """
    try:
        # Import the polygons_to_jsomr module dynamically
        poly_to_jsomr = import_module_from_file("polygons_to_jsomr", "polygons_to_jsomr.py")
        
        # Load polygon data
        polygon_data = poly_to_jsomr.load_polygon_data(polygon_file)
        logger.info(f"Loaded {len(polygon_data)} polygons from {polygon_file}")
        
        # Group polygons into potential staves
        grouped_staves = poly_to_jsomr.group_polygons_vertically(
            polygon_data, vertical_tolerance=vertical_tolerance
        )
        logger.info(f"Grouped polygons into {len(grouped_staves)} potential staves")
        
        # Convert grouped polygons to JSOMR format
        jsomr_output = poly_to_jsomr.convert_grouped_to_jsomr(grouped_staves)
        
        # Save the JSOMR file
        with open(output_jsomr, "w") as json_file:
            json.dump(jsomr_output, json_file, indent=2)
        
        logger.info(f"JSOMR file saved to: {output_jsomr}")
        return output_jsomr
        
    except Exception as e:
        logger.error(f"Error converting polygons to JSOMR: {e}")
        return None

def integrate_glyphs_with_jsomr(jsomr_file, xml_file, output_file):
    """
    Integrate glyph information from XML with staff information in JSOMR.
    
    Args:
        jsomr_file: Path to the JSOMR file
        xml_file: Path to the XML file with glyph information
        output_file: Path to save the integrated JSOMR file
    """
    try:
        # Import the glyph_to_jsomr_integration module dynamically
        glyph_integration = import_module_from_file(
            "glyph_to_jsomr_integration", "glyph_to_jsomr_integration.py"
        )
        
        # Run the integration function
        glyph_integration.integrate_glyphs_with_jsomr(jsomr_file, xml_file, output_file)
        logger.info(f"Successfully integrated glyphs with JSOMR and saved to {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error integrating glyphs with JSOMR: {e}")
        return None

def run_mei_encoding(jsomr_file, mei_mapping_csv, output_mei_file, neume_spacing=0.5, text_alignment=None, column_splitting=None):
    """
    Run the MEI encoding process.
    
    Args:
        jsomr_file: Path to the JSOMR file
        mei_mapping_csv: Path to the MEI mapping CSV
        output_mei_file: Path to save the output MEI file
        neume_spacing: Neume component spacing parameter
        text_alignment: Optional path to the text alignment JSON
        column_splitting: Optional path to the column splitting data
    """
    try:
        # Import the MEI_encoding module dynamically
        mei_encoding = import_module_from_file("MEI_encoding", "MEI_encoding.py")
        build_mei = import_module_from_file("build_mei_file", "build_mei_file.py")
        parse_classifier = import_module_from_file("parse_classifier_table", "parse_classifier_table.py")
        
        # Load the JSOMR file
        with open(jsomr_file, 'r') as file:
            jsomr = json.load(file)
        
        # Load text alignment if provided
        syls = None
        if text_alignment:
            with open(text_alignment, 'r') as file:
                syls = json.load(file)
        
        # Load column splitting data if provided
        split_ranges = None
        if column_splitting:
            with open(column_splitting, 'r') as file:
                split_ranges = json.load(file)
        
        # Fetch classifier table
        classifier_table, width_container = parse_classifier.fetch_table_from_csv(mei_mapping_csv)
        
        # Process the data to create MEI
        mei_string = build_mei.process(jsomr, syls, classifier_table, neume_spacing, width_container, split_ranges)
        
        # Write the MEI string to the output file
        with open(output_mei_file, 'w') as file:
            file.write(mei_string)
        
        logger.info(f"MEI file successfully written to {output_mei_file}")
        return output_mei_file
        
    except Exception as e:
        logger.error(f"Error running MEI encoding: {e}")
        return None

def fix_mei_coordinates(mei_file, jsomr_file, output_file):
    """
    Fix empty or incorrect zones in an MEI file by using coordinates from a JSOMR file.
    
    Args:
        mei_file: Path to the MEI file
        jsomr_file: Path to the JSOMR file with correct coordinates
        output_file: Path to save the fixed MEI file
    """
    try:
        # Import the fix_mei_coordinates module dynamically
        fix_mei = import_module_from_file("fix_mei_coordinates", "fix_mei_coordinates.py")
        
        # Run the coordinate fixing function
        fix_mei.fix_mei_coordinates(mei_file, jsomr_file, output_file)
        
        # Add missing system break elements if needed
        fix_mei.add_missing_sb_elements(output_file, output_file)
        
        logger.info(f"Fixed MEI file saved to {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error fixing MEI coordinates: {e}")
        return None

def run_pipeline(args):
    """
    Run the complete MEI pipeline.
    
    Args:
        args: Command line arguments
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir if args.output_dir else f"mei_output_{timestamp}"
    ensure_directory(output_dir)
    
    # Step 1: Convert polygons to JSOMR if polygon file is provided
    if args.polygon_file:
        jsomr_file = os.path.join(output_dir, "polygons_to_jsomr.json")
        logger.info("Step 1: Converting polygons to JSOMR")
        jsomr_file = run_polygons_to_jsomr(args.polygon_file, jsomr_file, args.vertical_tolerance)
        if not jsomr_file:
            logger.error("Failed to convert polygons to JSOMR. Pipeline stopped.")
            return False
    else:
        jsomr_file = args.jsomr_file
        if not jsomr_file:
            logger.error("No JSOMR file or polygon file provided. Pipeline stopped.")
            return False
    
    # Step 2: Integrate glyph information with JSOMR
    if args.glyph_xml:
        integrated_jsomr = os.path.join(output_dir, "integrated_jsomr.json")
        logger.info("Step 2: Integrating glyph information with JSOMR")
        integrated_jsomr = integrate_glyphs_with_jsomr(jsomr_file, args.glyph_xml, integrated_jsomr)
        if not integrated_jsomr:
            logger.error("Failed to integrate glyphs with JSOMR. Pipeline stopped.")
            return False
        jsomr_file = integrated_jsomr
    
    # Step 3: Run MEI encoding
    mei_file = os.path.join(output_dir, "output.mei")
    logger.info("Step 3: Running MEI encoding")
    mei_file = run_mei_encoding(
        jsomr_file, 
        args.mei_mapping_csv, 
        mei_file,
        args.neume_spacing,
        args.text_alignment,
        args.column_splitting
    )
    if not mei_file:
        logger.error("Failed to run MEI encoding. Pipeline stopped.")
        return False
    
    # Step 4: Fix MEI coordinates
    fixed_mei = os.path.join(output_dir, "fixed_output.mei")
    logger.info("Step 4: Fixing MEI coordinates")
    fixed_mei = fix_mei_coordinates(mei_file, jsomr_file, fixed_mei)
    if not fixed_mei:
        logger.error("Failed to fix MEI coordinates. Pipeline stopped.")
        return False
    
    # Step 5: Analyze the final MEI file
    fix_mei = import_module_from_file("fix_mei_coordinates", "fix_mei_coordinates.py")
    logger.info("Step 5: Analyzing final MEI file")
    fix_mei.analyze_mei_structure(fixed_mei)
    fix_mei.find_missing_sb_references(fixed_mei)
    
    logger.info(f"Pipeline completed successfully. Final MEI file: {fixed_mei}")
    return True

def main():
    """Main function to parse arguments and run the pipeline."""
    parser = argparse.ArgumentParser(description="Complete MEI Pipeline")
    
    # Input files
    input_group = parser.add_argument_group("Input Files")
    input_group.add_argument("--polygon-file", help="Path to polygon data file")
    input_group.add_argument("--jsomr-file", help="Path to existing JSOMR file (if not using polygon file)")
    input_group.add_argument("--glyph-xml", help="Path to XML file with glyph information")
    input_group.add_argument("--mei-mapping-csv", required=True, help="Path to MEI mapping CSV file")
    input_group.add_argument("--text-alignment", help="Path to text alignment JSON file")
    input_group.add_argument("--column-splitting", help="Path to column splitting data")
    
    # Output options
    output_group = parser.add_argument_group("Output Options")
    output_group.add_argument("--output-dir", help="Directory to save output files")
    
    # Configuration options
    config_group = parser.add_argument_group("Configuration")
    config_group.add_argument("--vertical-tolerance", type=int, default=100, 
                             help="Vertical tolerance for grouping staves (default: 100)")
    config_group.add_argument("--neume-spacing", type=float, default=0.5,
                             help="Neume component spacing parameter (default: 0.5)")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not args.polygon_file and not args.jsomr_file:
        parser.error("Either --polygon-file or --jsomr-file must be provided")
    
    if not args.mei_mapping_csv:
        parser.error("--mei-mapping-csv is required")
    
    # Run the pipeline
    success = run_pipeline(args)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())