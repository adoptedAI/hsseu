from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import pandas as pd
import json
import hashlib
import requests
from io import StringIO
import plotly.express as px
import plotly.graph_objects as go
import plotly.offline as pyo
import logging
import os
import traceback

# Create your views here.

def index(request):
    return render(request, 'hello/index.html')

def map_view(request):
    try:
        # Path to local CSV file
        csv_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Allied_Structures_Main_Canal.csv')
        
        df = None
        error_msg = None
        
        # Try to read from local CSV file
        try:
            df = pd.read_csv(csv_file_path)

            # Check for critical columns
            critical_cols = ['Lat', 'Long', 'Name', 'Canal', 'Division', 'Circle', 'Zone', 'Structure Type']
            missing_cols = [col for col in critical_cols if col not in df.columns]
            if missing_cols:
                print(f"Warning: Missing critical columns: {missing_cols}")
                
            # Check for null values in critical fields
            for col in ['Lat', 'Long']:
                if col in df.columns:
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        print(f"Warning: {null_count} null values in {col} column")
        except Exception as e:
            error_msg = f"Error loading CSV file: {str(e)}"
            print(error_msg)
        
        # If local file failed, create sample data
        if df is None:
            print("Creating sample data as fallback")
            # Create sample data with required columns
            data = {
                'Name': ['Sample Structure 1', 'Sample Structure 2', 'Sample Structure 3'],
                'Canal': ['Canal A', 'Canal B', 'Canal A'],
                'Division': ['Division X', 'Division Y', 'Division X'],
                'Circle': ['Circle 1', 'Circle 2', 'Circle 1'],
                'Zone': ['North Zone', 'South Zone', 'North Zone'],
                'Lat': [29.0, 29.2, 28.8],
                'Long': [71.0, 71.2, 70.8],
                'Structure Type': ['Type A', 'Type B', 'Type C']
            }
            df = pd.DataFrame(data)
        
        # Ensure 'Type' column
        df['Type'] = df['Structure Type']
        
        # Dropdown values
        unique_canals = sorted(df['Canal'].dropna().unique().tolist())
        unique_divisions = sorted(df['Division'].dropna().unique().tolist())
        unique_circles = sorted(df['Circle'].dropna().unique().tolist())
        unique_zones = sorted(df['Zone'].dropna().unique().tolist())
        
        # Color palette per canal
        def get_color(s): 
            return '#' + hashlib.md5(s.encode()).hexdigest()[:6]
        
        canal_colors = {c: get_color(c) for c in unique_canals}
        
        # Create GeoJSON
        features = []
        for _, row in df.iterrows():
            try:
                lat, lon = float(row['Lat']), float(row['Long'])
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": str(row['Name']),
                        "canal": str(row['Canal']),
                        "division": str(row['Division']),
                        "circle": str(row['Circle']),
                        "zone": str(row['Zone']),
                        "lat": lat,
                        "long": lon,
                        "color": canal_colors.get(row['Canal'], '#808080'),
                        "type": str(row['Type'])
                    },
                    "geometry": {"type": "Point", "coordinates": [lon, lat]}
                })
            except Exception as e:
                print(f"Error processing row: {e}")
                continue
        
        geojson_data = {"type": "FeatureCollection", "features": features}
        print(f"Created GeoJSON with {len(features)} features")
        geojson_str = json.dumps(geojson_data)
        
        # Pass to template with updated context
        context = {
            'geojson_str': geojson_str,  # This will be used with escapejs in the template
            'unique_zones': unique_zones,
            'unique_circles': unique_circles,
            'unique_divisions': unique_divisions,
            'unique_canals': unique_canals,
            'error_msg': error_msg
        }
        
        # Go back to using the fixed map.html template
        return render(request, 'hello/map.html', context)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in map_view: {str(e)}")
        print(error_trace)
        return HttpResponse(f"Error loading map data: {str(e)}")

def inspection_map_view(request):
    try:
        # Path to inspection data CSV file - using relative path from project root
        csv_file_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Inspection_data_base.csv')
        
        # Debug - check if file exists
        if os.path.exists(csv_file_path):
            print(f"Found CSV file at: {csv_file_path}")
        else:
            print(f"WARNING: File does not exist at: {csv_file_path}")
            # Try alternative paths
            alt_paths = [
                'Inspection_data_base.csv',
                './Inspection_data_base.csv'
            ]
            for path in alt_paths:
                if os.path.exists(path):
                    csv_file_path = path
                    print(f"Found CSV file at alternative path: {path}")
                    break
        
        df = None
        error_msg = None
        
        # Try to read from local CSV file
        try:
            # Try multiple encodings
            encodings = ['cp1252', 'utf-8', 'latin1']
            for encoding in encodings:
                try:
                    df = pd.read_csv(csv_file_path, encoding=encoding)
                    break
                except UnicodeDecodeError:
                    print(f"Failed with encoding: {encoding}")
                    continue
            
            if df is None:
                raise ValueError("Could not read CSV with any encoding")
                

            # Check for critical columns
            critical_cols = ['Latitude ', 'Longitude', 'Structure Name/Gate No', 'Division', 'Circle', 'Zone']
            missing_cols = [col for col in critical_cols if col not in df.columns]
            if missing_cols:
                print(f"Warning: Missing critical columns: {missing_cols}")
                
            # Map specific columns to standardized names to handle variations
            column_mapping = {}
            
            # Find year column
            year_cols = [col for col in df.columns if 'Year' in col]
            if year_cols:
                year_col = year_cols[0]
                column_mapping[year_col] = 'Inspection Year'
            else:
                print("Warning: No column containing 'Year' found")
                
            # Find type column
            type_cols = [col for col in df.columns if 'Type' in col and 'Year' not in col]
            if type_cols:
                type_col = type_cols[0]
                column_mapping[type_col] = 'Inspection Type'
            else:
                print("Warning: No column containing 'Type' found")
                
            # Find domain column
            domain_cols = [col for col in df.columns if col in ['Domain', 'E&I', 'Works']]
            if domain_cols:
                domain_col = domain_cols[0]
                column_mapping[domain_col] = 'Domain'
            else:
                print("Warning: No column for Domain found")
            
            # Find condition column - handle both 'Condition' and 'Condition / Health'
            condition_cols = [col for col in df.columns if col in ['Condition', 'Condition / Health']]
            if condition_cols:
                condition_col = condition_cols[0]
                column_mapping[condition_col] = 'Condition'
            else:
                # Also try looking for column K specifically which may contain condition data
                if 'K' in df.columns:
                    column_mapping['K'] = 'Condition'
                else:
                    print("Warning: No column for Condition found")
            
            # Apply column mapping if needed
            if column_mapping:
                df = df.rename(columns=column_mapping)
                
            # Check for null values in critical fields
            for col in ['Latitude ', 'Longitude']:
                if col in df.columns:
                    null_count = df[col].isnull().sum()
                    if null_count > 0:
                        print(f"Warning: {null_count} null values in {col} column")
            
            # Ensure required columns exist with defaults
            if 'Inspection Year' not in df.columns:
                df['Inspection Year'] = 'Unknown'
                
            if 'Inspection Type' not in df.columns:
                df['Inspection Type'] = 'Unknown'
                
            if 'Domain' not in df.columns:
                df['Domain'] = 'Unknown'
            
            if 'Condition' not in df.columns:
                df['Condition'] = 'Unknown'
            
        except Exception as e:
            error_msg = f"Error loading inspection CSV file: {str(e)}"
            print(error_msg)
        
        # If local file failed, create sample data
        if df is None:
            print("Creating sample inspection data as fallback")
            # Create sample data with required columns
            data = {
                'Structure Name/Gate No': ['Sample Gate 1', 'Sample Gate 2', 'Sample Gate 3'],
                'Division': ['Division X', 'Division Y', 'Division X'],
                'Circle': ['Circle 1', 'Circle 2', 'Circle 1'],
                'Zone': ['North Zone', 'South Zone', 'North Zone'],
                'Latitude ': [29.0, 29.2, 28.8],
                'Longitude': [71.0, 71.2, 70.8],
                'Domain': ['Type A', 'Type B', 'Type C'],
                'Inspection Type': ['Closure', 'Regular', 'Closure'],
                'Inspection Year': ['2022-2023', '2021-2022', '2022-2023'],
                'Condition / Health': ['Good', 'Poor', 'Fair'],
                'Issue/Problem': ['Issue 1', 'Issue 2', 'Issue 3'],
                'Recommendation': ['Rec 1', 'Rec 2', 'Rec 3']
            }
            df = pd.DataFrame(data)
        
        # Ensure all required columns exist with default values
        if 'Domain' not in df.columns:
            df['Domain'] = 'Unknown'
            
        # Map the domain/inspection type to the 'type' field for consistency with original map
        df['Type'] = df['Domain'].fillna('Unknown')
        
        # Dropdown values - using unique values from the inspection data
        unique_divisions = sorted(df['Division'].dropna().unique().tolist())
        unique_circles = sorted(df['Circle'].dropna().unique().tolist())
        unique_zones = sorted(df['Zone'].dropna().unique().tolist())
        unique_domains = sorted(df['Domain'].dropna().unique().tolist())
        unique_years = sorted(df['Inspection Year'].dropna().unique().tolist())
        unique_inspection_types = sorted(df['Inspection Type'].dropna().unique().tolist())
        unique_conditions = sorted(df['Condition'].dropna().unique().tolist())
        
        # Create GeoJSON
        features = []
        skipped_rows = 0
        for index, row in df.iterrows():
            try:
                # Handle potential missing or invalid coordinates
                if 'Latitude ' not in row or 'Longitude' not in row:
                    print(f"Missing coordinates in row {index}")
                    skipped_rows += 1
                    continue
                    
                try:
                    lat = float(row['Latitude '])
                    lon = float(row['Longitude'])
                    if lat == 0 or lon == 0 or pd.isna(lat) or pd.isna(lon):
                        print(f"Invalid coordinates in row {index}: {lat}, {lon}")
                        skipped_rows += 1
                        continue
                except (ValueError, TypeError):
                    print(f"Could not convert coordinates to float in row {index}")
                    skipped_rows += 1
                    continue
                
                # Handle potential missing values in inspection data
                structure_name = str(row.get('Structure Name/Gate No', 'Unknown'))
                division = str(row.get('Division', 'Unknown'))
                circle = str(row.get('Circle', 'Unknown'))
                zone = str(row.get('Zone', 'Unknown'))
                domain = str(row.get('Domain', 'Unknown'))
                inspection_type = str(row.get('Inspection Type', 'Unknown'))
                inspection_year = str(row.get('Inspection Year', 'Unknown'))
                condition = str(row.get('Condition', 'Unknown'))
                issue = str(row.get('Issue/Problem', 'Unknown'))
                recommendation = str(row.get('Recommendation', 'Unknown'))
                
                features.append({
                    "type": "Feature",
                    "properties": {
                        "name": structure_name,
                        "division": division,
                        "circle": circle,
                        "zone": zone,
                        "lat": lat,
                        "long": lon,
                        "color": "#808080",  # Default color, will be set by the client
                        "type": domain,
                        "domain": domain,
                        "inspection_type": inspection_type,
                        "inspection_year": inspection_year,
                        "condition": condition,
                        "issue": issue,
                        "recommendation": recommendation,
                        "canal": inspection_year  # Use inspection year as canal for compatibility
                    },
                    "geometry": {"type": "Point", "coordinates": [lon, lat]}
                })
            except Exception as e:
                print(f"Error processing inspection row {index}: {e}")
                skipped_rows += 1
                continue
        
        print(f"Processed {len(features)} features, skipped {skipped_rows} rows")
        geojson_data = {"type": "FeatureCollection", "features": features}
        print(f"Created inspection GeoJSON with {len(features)} features")
        geojson_str = json.dumps(geojson_data)
        
        # Pass to template with updated context
        context = {
            'geojson_str': geojson_str,
            'unique_zones': unique_zones,
            'unique_circles': unique_circles,
            'unique_divisions': unique_divisions,
            'unique_canals': unique_years,  # Using inspection years as canals for UI compatibility
            'unique_domains': unique_domains,
            'unique_inspection_types': unique_inspection_types,
            'unique_conditions': unique_conditions,
            'is_inspection_data': True,  # Flag to indicate this is inspection data
            'error_msg': error_msg
        }
        
        # Use the inspection map template
        return render(request, 'hello/inspection_map.html', context)
        
    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"Error in inspection_map_view: {str(e)}")
        print(error_trace)
        return HttpResponse(f"Error loading inspection map data: {str(e)}")
