import os
import re
import sys
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

from sklearn.preprocessing import StandardScaler
from scipy.spatial.distance import euclidean

class CRLAv2:
    """
    Classroom Reading Level Assessment (CRLA) data analysis class.
    
    This class handles the processing, analysis, and visualization of 
    reading assessment data for Grades 1-3, comparing beginning of school year (BoSY)
    and end of school year (EoSY) results to measure educational progress.
    """
    
    def __init__(self):
        """Initialize the CRLA class."""
        # Initialize data containers
        self.validation_data = None
        self.combined_percentage_data = None
        self.combined_raw_data = None
        self.processed_tables = None
        self.component_model = None

    def load_assessment_data(
        self,
        directory_path=None,
        bosy_filename=None,
        eosy_filename=None
    ):
        """
        Load Beginning of School Year (BoSY) and End of School Year (EoSY) assessment data.
        
        Parameters
        ----------
        directory_path : str, optional
            Path to the directory containing the data files
        bosy_filename : str, optional
            Filename for the Beginning of School Year data
        eosy_filename : str, optional
            Filename for the End of School Year data
            
        Returns
        -------
        tuple
            (bosy_dataframe, eosy_dataframe) containing the loaded assessment data
        """
        data_directory = '../datasets' if directory_path is None else directory_path
        bosy_file = '_CRLA National Dashboard_BoSY 2024-25 Assessment Results_Table.csv' if bosy_filename is None else bosy_filename
        eosy_file = '_CRLA National Dashboard_EoSY 2024-25 Assessment Results_Table.csv' if eosy_filename is None else eosy_filename
        
        bosy_path = os.path.join(data_directory, bosy_file)
        eosy_path = os.path.join(data_directory, eosy_file)

        bosy_dataframe = pd.read_csv(bosy_path, low_memory=False)
        eosy_dataframe = pd.read_csv(eosy_path, low_memory=False)

        return bosy_dataframe, eosy_dataframe
        
    def extract_column_structures(self, assessment_dataframe):
        """
        Extract identification columns and grade-specific data columns from assessment data.
        
        Parameters
        ----------
        assessment_dataframe : pandas.DataFrame
            Assessment data to extract columns from
            
        Returns
        -------
        tuple
            (identifier_columns, grade_columns_dict) where:
            - identifier_columns: list of column names that identify schools
            - grade_columns_dict: dictionary mapping grade levels to their data columns
        """
        dataframe = assessment_dataframe.copy()
        
        # Columns that identify schools (Region, Division, District, School ID, School Name)
        identifier_columns = dataframe.loc[:,'Region':'School Name'].columns.tolist()
        
        # Columns containing assessment data
        data_columns = dataframe.loc[:,'G1 Total Assessed':].columns.tolist()
        # Remove aggregate columns containing "Total"
        data_columns = [col for col in data_columns if 'total' not in col.lower()]
        
        # Organize columns by grade level
        grades = ['G1', 'G2', 'G3']
        grade_columns_dict = {}
        for grade in grades:
            grade_columns_dict[grade] = [col for col in data_columns if grade in col]

        return identifier_columns, grade_columns_dict

    def create_school_identifier_table(self, identifier_columns, assessment_dataframes):
        """
        Create a unified table of school identifiers from both BoSY and EoSY data.
        
        Parameters
        ----------
        identifier_columns : list
            List of column names that identify schools
        assessment_dataframes : list
            List containing [bosy_dataframe, eosy_dataframe]
            
        Returns
        -------
        pandas.DataFrame
            Table of school identifiers with School ID as index
        """
        # Combine school identifiers from both BoSY and EoSY
        school_identifiers = pd.concat(
            [
                assessment_dataframes[0][identifier_columns], # BoSY dataframe
                assessment_dataframes[1][identifier_columns]  # EoSY dataframe
            ]
        )
        
        # Remove duplicate schools, keeping first occurrence
        duplicate_mask = school_identifiers.duplicated(subset=['School ID'])
        school_identifiers = school_identifiers[~duplicate_mask].copy().set_index('School ID')
        
        return school_identifiers

    def create_grade_data_tables(
        self,
        assessment_dataframes,
        school_identifiers,
        grade_columns_dict,
        regex_patterns=[
            r'(^G1) (\b.*\w$)',
            r'(^G2) (MT|Fil) (\b.*$)',
            r'(^G3) (MT|Fil|Eng) (\b.*$)',
        ]
    ):
        """
        Create grade-specific data tables from assessment data.
        
        Parameters
        ----------
        assessment_dataframes : list
            List containing [bosy_dataframe, eosy_dataframe]
        school_identifiers : pandas.DataFrame
            Table of school identifiers created by create_school_identifier_table
        grade_columns_dict : dict
            Dictionary mapping grade levels to their data columns
        regex_patterns : list, optional
            List of regex patterns to extract components from column headers for each grade
            
        Returns
        -------
        dict
            Dictionary mapping grade levels to their processed data tables
        """
        grades = list(grade_columns_dict.keys())
        periods = ['BoSY', 'EoSY']
        grade_tables = {}
        
        for grade, pattern in zip(grades, regex_patterns):
            grade_period_dataframes = []
            
            for period_index, dataframe in enumerate(assessment_dataframes):
                # Extract relevant columns for this grade and set School ID as index
                grade_data = dataframe.set_index('School ID')[grade_columns_dict[grade]]
                
                # Clean data: handle commas and missing values
                for column in grade_data.columns:
                    grade_data[column] = grade_data[column].astype(str).str.replace(',', '')
                    grade_data[column] = grade_data[column].astype(str).str.replace('-', str(np.nan))
                    grade_data[column] = pd.to_numeric(grade_data[column], errors='coerce')
                
                # Transform to long format for easier analysis
                melted_data = grade_data.reset_index().melt(
                    id_vars='School ID',
                    value_vars=grade_columns_dict[grade],
                    var_name='original_column_name',
                    value_name='student_count'
                )

                # Parse column names into component parts
                if grade == "G1":
                    melted_data[['grade_level', 'reading_profile']] = melted_data['original_column_name'].str.extract(pattern)
                elif grade == "G2":
                    # Fix typo in column name
                    melted_data['original_column_name'] = melted_data['original_column_name'].replace(
                        {'G2 FIl Higher Emergent': 'G2 Fil Higher Emergent'}
                    )
                    melted_data[['grade_level', 'language', 'reading_profile']] = melted_data['original_column_name'].str.extract(pattern)
                elif grade == "G3":
                    # Fix typo in column name
                    melted_data['original_column_name'] = melted_data['original_column_name'].replace(
                        {'G3 FIl Higher Emergent': 'G3 Fil Higher Emergent'}
                    )
                    melted_data[['grade_level', 'language', 'reading_profile']] = melted_data['original_column_name'].str.extract(pattern)
        
                # Add period label (BoSY or EoSY)
                melted_data['assessment_period'] = periods[period_index]
                
                grade_period_dataframes.append(melted_data)

            # Combine data from both periods
            combined_grade_data = pd.concat(grade_period_dataframes)
            
            # Add school identification information
            grade_table = (
                combined_grade_data
                .set_index('School ID')
                .join(school_identifiers)
                .reset_index()
            )

            grade_tables[grade] = grade_table

        return grade_tables

    def calculate_raw_and_percentage_data(self, grade_tables, groupby_column="School ID"):
        """
        Calculate raw counts and percentages of students in each reading profile category.
        
        Parameters
        ----------
        grade_tables : dict
            Dictionary of grade-specific data tables from create_grade_data_tables
        groupby_column : str, optional
            Column to use for grouping (e.g., "School ID", "Region")
            
        Returns
        -------
        dict
            Dictionary containing processed tables for each grade with raw counts and percentages
        """
        processed_tables = {}
        
        for grade, grade_table in grade_tables.items():
            if grade == "G1":
                # Create pivot table with assessment_period and reading_profile as columns
                pivot_columns = ['assessment_period', 'reading_profile']
                
                # Raw count of learners in each reading profile
                pivot_table = grade_table.pivot_table(
                    index=groupby_column,
                    columns=pivot_columns,
                    values='student_count',
                    aggfunc='sum'
                )
                
                # Split into BoSY and EoSY data
                bosy_counts = pivot_table.iloc[:, :5]  # First 5 columns are BoSY
                eosy_counts = pivot_table.iloc[:, 5:]  # Remaining columns are EoSY
                
                # Calculate percentages
                bosy_percentages = bosy_counts.copy()
                eosy_percentages = eosy_counts.copy()
                
                # Calculate percentage for each school
                for index in bosy_percentages.index:
                    row_sum = bosy_counts.loc[index, :].sum()
                    if row_sum > 0:  # Prevent division by zero
                        bosy_percentages.loc[index, :] = (bosy_counts.loc[index, :] / row_sum) * 100
                    
                    row_sum = eosy_counts.loc[index, :].sum()
                    if row_sum > 0:  # Prevent division by zero
                        eosy_percentages.loc[index, :] = (eosy_counts.loc[index, :] / row_sum) * 100
            
                processed_tables[grade] = [bosy_counts, eosy_counts, bosy_percentages, eosy_percentages]

            elif grade == "G2":
                pivot_columns = ['assessment_period', 'language', 'reading_profile']
                processed_tables[grade] = self._process_grade2_data(grade_table, pivot_columns, groupby_column)

            elif grade == "G3":
                pivot_columns = ['assessment_period', 'language', 'reading_profile']
                processed_tables[grade] = self._process_grade3_data(grade_table, pivot_columns, groupby_column)

        return processed_tables

    def _process_grade2_data(self, grade_table, pivot_columns, groupby_column='School ID'):
        """
        Process Grade 2 data to calculate raw counts and percentages by language.
        
        Parameters
        ----------
        grade_table : pandas.DataFrame
            Grade 2 data table
        pivot_columns : list
            Columns to use for pivoting
        groupby_column : str
            Column to group by (e.g., "School ID", "Region")
            
        Returns
        -------
        list
            [bosy_counts, eosy_counts, bosy_percentages, eosy_percentages]
        """
        pivot_table = grade_table.pivot_table(
            index=groupby_column,
            columns=pivot_columns,
            values='student_count',
            aggfunc='sum'
        )
        
        # Split into BoSY and EoSY data
        bosy_counts = pivot_table.iloc[:, :10]  # First 10 columns are BoSY (5 for Fil, 5 for MT)
        eosy_counts = pivot_table.iloc[:, 10:]  # Remaining columns are EoSY
        
        bosy_percentages = bosy_counts.copy()
        eosy_percentages = eosy_counts.copy()
        
        fil_columns = 5  # Number of columns for Filipino language
        
        # Calculate percentages for BoSY, Filipino language
        for index, row in bosy_counts.iloc[:, :fil_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                bosy_percentages.iloc[bosy_counts.index.get_loc(index), :fil_columns] = (row / row_sum) * 100
                
        # Calculate percentages for BoSY, Mother Tongue language
        for index, row in bosy_counts.iloc[:, fil_columns:].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                bosy_percentages.iloc[bosy_counts.index.get_loc(index), fil_columns:] = (row / row_sum) * 100

        # Calculate percentages for EoSY, Filipino language
        for index, row in eosy_counts.iloc[:, :fil_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                eosy_percentages.iloc[eosy_counts.index.get_loc(index), :fil_columns] = (row / row_sum) * 100
                
        # Calculate percentages for EoSY, Mother Tongue language
        for index, row in eosy_counts.iloc[:, fil_columns:].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                eosy_percentages.iloc[eosy_counts.index.get_loc(index), fil_columns:] = (row / row_sum) * 100

        return [bosy_counts, eosy_counts, bosy_percentages, eosy_percentages]

    def _process_grade3_data(self, grade_table, pivot_columns, groupby_column='School ID'):
        """
        Process Grade 3 data to calculate raw counts and percentages by language.
        
        Parameters
        ----------
        grade_table : pandas.DataFrame
            Grade 3 data table
        pivot_columns : list
            Columns to use for pivoting
        groupby_column : str
            Column to group by (e.g., "School ID", "Region")
            
        Returns
        -------
        list
            [bosy_counts, eosy_counts, bosy_percentages, eosy_percentages]
        """
        pivot_table = grade_table.pivot_table(
            index=groupby_column,
            columns=pivot_columns,
            values='student_count',
            aggfunc='sum'
        )
        
        # Split into BoSY and EoSY data
        bosy_counts = pivot_table.iloc[:, :15]  # First 15 columns are BoSY (5 for each language)
        eosy_counts = pivot_table.iloc[:, 15:]  # Remaining columns are EoSY
        
        bosy_percentages = bosy_counts.copy()
        eosy_percentages = eosy_counts.copy()
        
        language_columns = 5  # Number of columns for each language
        
        # Calculate percentages for BoSY data
        # English language (first 5 columns)
        for index, row in bosy_counts.iloc[:, :language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                bosy_percentages.iloc[bosy_counts.index.get_loc(index), :language_columns] = (row / row_sum) * 100
                
        # Filipino language (next 5 columns)
        for index, row in bosy_counts.iloc[:, language_columns:2*language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                bosy_percentages.iloc[bosy_counts.index.get_loc(index), language_columns:2*language_columns] = (row / row_sum) * 100
                
        # Mother Tongue language (next 5 columns)
        for index, row in bosy_counts.iloc[:, 2*language_columns:3*language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                bosy_percentages.iloc[bosy_counts.index.get_loc(index), 2*language_columns:3*language_columns] = (row / row_sum) * 100
        
        # Calculate percentages for EoSY data
        # English language (first 5 columns)
        for index, row in eosy_counts.iloc[:, :language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                eosy_percentages.iloc[eosy_counts.index.get_loc(index), :language_columns] = (row / row_sum) * 100
                
        # Filipino language (next 5 columns)
        for index, row in eosy_counts.iloc[:, language_columns:2*language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                eosy_percentages.iloc[eosy_counts.index.get_loc(index), language_columns:2*language_columns] = (row / row_sum) * 100
                
        # Mother Tongue language (next 5 columns)
        for index, row in eosy_counts.iloc[:, 2*language_columns:3*language_columns].iterrows():
            row_sum = row.sum()
            if row_sum > 0:  # Prevent division by zero
                eosy_percentages.iloc[eosy_counts.index.get_loc(index), 2*language_columns:3*language_columns] = (row / row_sum) * 100

        return [bosy_counts, eosy_counts, bosy_percentages, eosy_percentages]

    def combine_grade_data(self, bosy_dataframes, eosy_dataframes, school_identifiers):
        """
        Combine data from all grades into a single dataframe for each period.
        Can be used for both raw counts or percentages.
        
        Parameters
        ----------
        bosy_dataframes : list
            List of BoSY dataframes for G1, G2, G3
        eosy_dataframes : list
            List of EoSY dataframes for G1, G2, G3
        school_identifiers : pandas.DataFrame
            Table of school identifiers
            
        Returns
        -------
        dict
            Dictionary containing 'BoSY' and 'EoSY' dataframes with combined data
        """
        combined_data = {}
        
        # Process BoSY data
        # Flatten multi-level column headers for Grade 1
        g1_bosy = bosy_dataframes[0].copy()
        g1_bosy.columns = ['G1_' + col[1] for col in g1_bosy.columns]
        
        # Flatten multi-level column headers for Grade 2
        g2_bosy = bosy_dataframes[1].copy()
        g2_bosy.columns = ['G2_' + '_'.join([col[1], col[2]]) for col in g2_bosy.columns]
        
        # Flatten multi-level column headers for Grade 3
        g3_bosy = bosy_dataframes[2].copy()
        g3_bosy.columns = ['G3_' + '_'.join([col[1], col[2]]) for col in g3_bosy.columns]
        
        # Combine all BoSY grade data horizontally
        bosy_combined = pd.concat(
            [g1_bosy, g2_bosy, g3_bosy],
            axis=1
        )
        
        # Process EoSY data similarly
        g1_eosy = eosy_dataframes[0].copy()
        g1_eosy.columns = ['G1_' + col[1] for col in g1_eosy.columns]
        
        g2_eosy = eosy_dataframes[1].copy()
        g2_eosy.columns = ['G2_' + '_'.join([col[1], col[2]]) for col in g2_eosy.columns]
        
        g3_eosy = eosy_dataframes[2].copy()
        g3_eosy.columns = ['G3_' + '_'.join([col[1], col[2]]) for col in g3_eosy.columns]
        
        # Combine all EoSY grade data horizontally
        eosy_combined = pd.concat(
            [g1_eosy, g2_eosy, g3_eosy],
            axis=1
        )
        
        # Join with school identifiers to add school metadata
        metadata_columns = ['School Name', 'Region', 'Division', 'District']
        bosy_combined = bosy_combined.join(school_identifiers[metadata_columns])
        eosy_combined = eosy_combined.join(school_identifiers[metadata_columns])
        
        # Reorder columns to put School Name first, followed by Region, Division, District
        other_columns = [col for col in bosy_combined.columns if col not in metadata_columns]
        column_order = metadata_columns + other_columns
        bosy_combined = bosy_combined[column_order]
        eosy_combined = eosy_combined[column_order]
        
        combined_data['BoSY'] = bosy_combined
        combined_data['EoSY'] = eosy_combined
        
        return combined_data
        
    def extract_data_by_period(self, processed_tables, data_type='percentages'):
        """
        Extract data of specified type from processed tables for both periods.
        
        Parameters
        ----------
        processed_tables : dict
            Dictionary of processed tables from calculate_raw_and_percentage_data
        data_type : str, optional
            Type of data to extract: 'raw' for raw counts, 'percentages' for percentages
            
        Returns
        -------
        tuple
            (bosy_dataframes, eosy_dataframes) containing lists of dataframes for each grade
        """
        # Determine indices based on data type
        if data_type == 'raw':
            bosy_index, eosy_index = 0, 1  # Raw counts
        else:  # 'percentages' is the default
            bosy_index, eosy_index = 2, 3  # Percentages
            
        # Extract dataframes for each period
        bosy_dataframes = [
            processed_tables['G1'][bosy_index],
            processed_tables['G2'][bosy_index],
            processed_tables['G3'][bosy_index]
        ]
        
        eosy_dataframes = [
            processed_tables['G1'][eosy_index],
            processed_tables['G2'][eosy_index],
            processed_tables['G3'][eosy_index]
        ]
        
        return bosy_dataframes, eosy_dataframes

    def validate_assessment_data(self, bosy_data, eosy_data, raw_count_data=None, threshold=0.25):
        """
        Validate school data to identify problematic cases for analysis.
        
        Parameters
        ----------
        bosy_data : pandas.DataFrame
            Beginning of School Year percentage data
        eosy_data : pandas.DataFrame
            End of School Year percentage data
        raw_count_data : dict, optional
            Dictionary containing raw count data for both periods
        threshold : float, optional
            Maximum acceptable difference in student counts (as a proportion)
            
        Returns
        -------
        pandas.DataFrame
            DataFrame with validation flags for each school
        """
        # Create validation dataframe with school IDs as index
        validation = pd.DataFrame(index=list(set(bosy_data.index) | set(eosy_data.index)))
        
        # Flag 1: Missing data for either period
        validation['has_bosy_data'] = validation.index.isin(bosy_data.index)
        validation['has_eosy_data'] = validation.index.isin(eosy_data.index)
        validation['complete_data'] = validation['has_bosy_data'] & validation['has_eosy_data']
        
        # Flag 2: Check for significant differences in student counts
        if raw_count_data is not None:
            bosy_counts = raw_count_data['BoSY']
            eosy_counts = raw_count_data['EoSY']
            
            # Calculate total assessed students for each school in each period
            validation['bosy_student_count'] = 0
            validation['eosy_student_count'] = 0
            
            # Sum across grade levels and subjects for schools that have data
            metadata_cols = ['School Name', 'Region', 'Division', 'District']
            for idx in validation.index:
                if idx in bosy_counts.index:
                    count_cols = [col for col in bosy_counts.columns if col not in metadata_cols]
                    # Handle both single and multiple columns cases
                    if len(count_cols) == 1:
                        # Single column case
                        validation.loc[idx, 'bosy_student_count'] = bosy_counts.loc[idx, count_cols[0]]
                    else:
                        # Multiple columns case
                        row_data = bosy_counts.loc[idx, count_cols]
                        total = row_data.values.sum() if isinstance(row_data, pd.Series) else row_data.sum().sum()
                        validation.loc[idx, 'bosy_student_count'] = total
                
                # Handle EoSY counts
                if idx in eosy_counts.index:
                    count_cols = [col for col in eosy_counts.columns if col not in metadata_cols]
                    # Handle both single and multiple columns cases
                    if len(count_cols) == 1:
                        # Single column case
                        validation.loc[idx, 'eosy_student_count'] = eosy_counts.loc[idx, count_cols[0]]
                    else:
                        # Multiple columns case
                        row_data = eosy_counts.loc[idx, count_cols]
                        total = row_data.values.sum() if isinstance(row_data, pd.Series) else row_data.sum().sum()
                        validation.loc[idx, 'eosy_student_count'] = total
            
            # Calculate percent difference for schools with both periods
            has_both = validation['complete_data']
            # Avoid division by zero
            validation.loc[has_both, 'count_difference'] = 0
            nonzero_counts = has_both & (validation['bosy_student_count'] > 0)
            
            if any(nonzero_counts):
                validation.loc[nonzero_counts, 'count_difference'] = abs(
                    validation.loc[nonzero_counts, 'eosy_student_count'] - 
                    validation.loc[nonzero_counts, 'bosy_student_count']
                ) / validation.loc[nonzero_counts, 'bosy_student_count']
            
            # Flag schools with significant count differences
            validation['count_mismatch'] = validation['count_difference'] > threshold
        
        # Overall validation flag
        if raw_count_data is not None:
            validation['valid_for_progress'] = validation['complete_data'] & ~validation['count_mismatch']
        else:
            validation['valid_for_progress'] = validation['complete_data']
        
        # Add metadata if available
        metadata_cols = ['School Name', 'Region', 'Division', 'District']
        for col in metadata_cols:
            if col in bosy_data.columns:
                validation[col] = None
                for idx in validation.index:
                    if idx in bosy_data.index:
                        validation.loc[idx, col] = bosy_data.loc[idx, col]
                    elif idx in eosy_data.index:
                        validation.loc[idx, col] = eosy_data.loc[idx, col]
        
        return validation

    def analyze_reading_performance(self, processed_tables, combined_raw_data, combined_percentage_data, custom_weights=None):
        """
        Comprehensive analysis of reading performance with data validation.
        
        Parameters
        ----------
        processed_tables : dict
            Dictionary of processed tables from calculate_raw_and_percentage_data
        combined_raw_data : dict
            Dictionary containing combined raw count data
        combined_percentage_data : dict
            Dictionary containing combined percentage data
        custom_weights : dict, optional
            Custom weights for each reading profile category
            
        Returns
        -------
        dict
            Dictionary containing analysis results
        """
        # Validate data quality
        validation = self.validate_assessment_data(
            combined_percentage_data['BoSY'], 
            combined_percentage_data['EoSY'],
            combined_raw_data,
            threshold=0.25  # 25% difference in student counts is flagged
        )
        
        # Store data for future use
        self.validation_data = validation
        self.combined_percentage_data = combined_percentage_data
        self.combined_raw_data = combined_raw_data
        self.processed_tables = processed_tables
        
        # Calculate performance scores
        bosy_scores = self.calculate_performance_score(
            combined_percentage_data['BoSY'], 
            validation,
            custom_weights
        )
        
        eosy_scores = self.calculate_performance_score(
            combined_percentage_data['EoSY'], 
            validation,
            custom_weights
        )
        
        # Calculate progress for valid schools
        progress_scores = self.calculate_progress_score(
            combined_percentage_data['BoSY'],
            combined_percentage_data['EoSY'],
            validation,
            custom_weights
        )
        
        # Create results dataframe
        results = pd.DataFrame(index=validation.index)
        metadata_cols = ['School Name', 'Region', 'Division', 'District']
        for col in metadata_cols:
            if col in validation.columns:
                results[col] = validation[col]
                
        results['Has BoSY Data'] = validation['has_bosy_data']
        results['Has EoSY Data'] = validation['has_eosy_data']
        
        if 'count_mismatch' in validation.columns:
            results['Student Count Mismatch'] = validation['count_mismatch']
        
        results['Valid for Progress Analysis'] = validation['valid_for_progress']
        results['BoSY Performance'] = bosy_scores
        results['EoSY Performance'] = eosy_scores
        results['Progress Score'] = progress_scores
        
        # Define all reading profile categories
        categories = ['Developing', 'Transitioning', 'Higher Emergent', 'Lower Emergent', 'Grade Level']
        
        # Add individual category columns from both periods for detailed breakdown
        for period in ['BoSY', 'EoSY']:
            period_data = combined_percentage_data[period]
            
            # For each category, add both averaged and individual columns
            for category in categories:
                # Find all columns for this category
                cat_cols = [col for col in period_data.columns 
                          if category in col and col not in metadata_cols]
                
                if cat_cols:
                    # Add average value across all columns for this category
                    results[f'{period} {category} %'] = period_data[cat_cols].mean(axis=1)
                    
                    # Add individual columns for detailed inspection
                    for col in cat_cols:
                        # Create a shorter column name that still identifies the data
                        short_col = col.replace('_', ' ')
                        if len(cat_cols) > 1:  # Only add individual columns if there's more than one
                            results[f'{period} {short_col}'] = period_data[col]
            
            # Add the weighted score calculation components
            if custom_weights is not None:
                # Calculate the weighted values for each category
                for category, weight in custom_weights.items():
                    cat_cols = [col for col in period_data.columns 
                              if category in col and col not in metadata_cols]
                    
                    if cat_cols:
                        category_avg = period_data[cat_cols].mean(axis=1)
                        results[f'{period} {category} Weighted'] = category_avg * weight / 100
        
        # Add weights used for the performance score calculation
        if custom_weights is not None:
            weight_str = ', '.join([f"{k}: {v}" for k, v in custom_weights.items()])
            print(f"Performance calculated using weights: {weight_str}")
        
        return {
            'results': results,
            'validation': validation,
            'weights_used': custom_weights
        }

    
    def calculate_performance_score(self, school_data, validation=None, custom_weights=None):
        """
        Calculate a weighted performance score that works with incomplete data.
        
        Parameters
        ----------
        school_data : pandas.DataFrame
            DataFrame containing percentages of students in each reading category
        validation : pandas.DataFrame, optional
            Validation data to identify problematic schools
        custom_weights : dict, optional
            Custom weights for each reading profile category
            
        Returns
        -------
        pandas.Series
            Series containing performance scores for each school
        """
        # Define default weights for each category
        default_weights = {
            'Developing': 100,
            'Transitioning': 100,
            'Higher Emergent': 100,
            'Lower Emergent': 100,
            'Grade Level': 100
        }
        
        # Use custom weights if provided
        weights = custom_weights if custom_weights is not None else default_weights
        
        scores = pd.Series(0.0, index=school_data.index)
        divisor = pd.Series(0.0, index=school_data.index)
        
        # Calculate weighted sum across all categories
        metadata_cols = ['School Name', 'Region', 'Division', 'District']
        for category, weight in weights.items():
            # Find all columns containing this category
            category_columns = [col for col in school_data.columns 
                               if category in col and col not in metadata_cols]
            
            for col in category_columns:
                # Handle missing data
                valid_data = ~school_data[col].isna()
                scores.loc[valid_data] += school_data.loc[valid_data, col] * weight / 100
                divisor.loc[valid_data] += weight
        
        # Normalize by sum of weights for valid data
        normalized_scores = scores / (divisor / 100)
        
        # Mark invalid scores as NaN
        if validation is not None:
            normalized_scores.loc[~validation.index.isin(school_data.index)] = np.nan
        
        return normalized_scores

    def calculate_progress_score(self, bosy_data, eosy_data, validation, custom_weights=None):
        """
        Calculate progress score only for schools with valid data in both periods.
        
        Parameters
        ----------
        bosy_data : pandas.DataFrame
            Beginning of School Year data
        eosy_data : pandas.DataFrame
            End of School Year data
        validation : pandas.DataFrame
            Validation data to identify which schools have valid data
        custom_weights : dict, optional
            Custom weights for each reading profile category
            
        Returns
        -------
        pandas.Series
            Series containing progress scores for valid schools
        """
        # Calculate individual period scores
        bosy_scores = self.calculate_performance_score(bosy_data, validation, custom_weights)
        eosy_scores = self.calculate_performance_score(eosy_data, validation, custom_weights)
        
        # Create progress series with all schools
        all_schools = set(bosy_data.index) | set(eosy_data.index)
        progress = pd.Series(np.nan, index=all_schools)
        
        # Calculate progress only for valid schools
        valid_schools = validation[validation['valid_for_progress']].index
        common_schools = set(valid_schools) & set(bosy_scores.index) & set(eosy_scores.index)
        
        for school in common_schools:
            progress[school] = eosy_scores[school] - bosy_scores[school]
        
        return progress

    def optimize_weights_from_pca(self, combined_percentage_data=None, validation=None, invert=False):
        """
        Derive optimal weights from PCA loadings on the first principal component,
        using only schools that are valid for progress analysis.
        
        Parameters
        ----------
        combined_percentage_data : dict, optional
            Dictionary containing 'BoSY' and 'EoSY' dataframes with percentage data.
            If None, uses the stored self.combined_percentage_data.
        validation : pandas.DataFrame, optional
            Validation data containing the 'valid_for_progress' column.
            If None, uses the stored self.validation_data.
        invert : bool, optional
            If True, invert the direction of weights for all categories except 'Grade Level'
            when 'Developing' has lower loading than 'Lower Emergent'.
            If False, use the PCA loadings as they are with no inversion.
            
        Returns
        -------
        dict
            Dictionary of optimized weights for each reading profile category
        """
        from sklearn.decomposition import PCA
        from sklearn.preprocessing import StandardScaler
        
        # Check if we have data to work with
        if combined_percentage_data is None:
            if self.combined_percentage_data is None:
                print("Error: No percentage data available. Run analyze_reading_performance first or provide combined_percentage_data.")
                return {
                    'Developing': 100,
                    'Transitioning': 100, 
                    'Higher Emergent': 100,
                    'Lower Emergent': 100,
                    'Grade Level': 100
                }
            combined_percentage_data = self.combined_percentage_data
            
        if validation is None:
            if self.validation_data is None:
                print("Error: No validation data available. Run analyze_reading_performance first or provide validation data.")
                return {
                    'Developing': 100,
                    'Transitioning': 100, 
                    'Higher Emergent': 100,
                    'Lower Emergent': 100,
                    'Grade Level': 100
                }
            validation = self.validation_data
        
        # Get only the valid schools for progress analysis
        valid_schools = validation[validation['valid_for_progress']].index
        if len(valid_schools) < 10:
            print(f"Warning: Only {len(valid_schools)} valid schools available for PCA. Results may not be reliable.")
        
        # Filter data to include only valid schools
        eosy_valid = combined_percentage_data['EoSY'].loc[valid_schools].copy()
        
        # Define the reading profile categories
        categories = ['Developing', 'Transitioning', 'Higher Emergent', 'Lower Emergent', 'Grade Level']
        metadata_cols = ['School Name', 'Region', 'Division', 'District']
        
        # Extract reading profile columns
        profile_columns = []
        for category in categories:
            cols = [col for col in eosy_valid.columns 
                  if category in col and col not in metadata_cols]
            profile_columns.extend(cols)
        
        # Make sure we have enough columns for PCA
        if len(profile_columns) < 5:
            print("Warning: Not enough profile columns found. Using default weights.")
            return {
                'Developing': 100,
                'Transitioning': 100, 
                'Higher Emergent': 100,
                'Lower Emergent': 100,
                'Grade Level': 100
            }
        
        # Get data and drop any rows with NaN values
        X = eosy_valid[profile_columns].dropna()
        if X.shape[0] < 5:
            print("Warning: Not enough complete data rows for PCA. Using default weights.")
            return {
                'Developing': 100,
                'Transitioning': 100, 
                'Higher Emergent': 100,
                'Lower Emergent': 100,
                'Grade Level': 100
            }
        
        # Standardize data
        X_scaled = StandardScaler().fit_transform(X)
        
        # Perform PCA
        pca = PCA(n_components=1)
        pca.fit(X_scaled)
    
        self.component_model = pca
        
        # Extract loadings of first principal component
        loadings = pca.components_[0]
        
        # Map loadings to categories
        category_loadings = {}
        col_idx = 0
        for category in categories:
            cols = [col for col in eosy_valid.columns 
                  if category in col and col not in metadata_cols]
            if len(cols) > 0:
                category_loadings[category] = np.mean([loadings[col_idx + i] for i in range(len(cols))])
                col_idx += len(cols)
        
        # Handle inversion logic based on the invert parameter
        if invert:
            # Check if higher proficiency levels have lower loadings
            if ('Developing' in category_loadings and 'Lower Emergent' in category_loadings and 
                category_loadings['Developing'] < category_loadings['Lower Emergent']):
                # Invert all categories except Grade Level
                for category in category_loadings:
                    if category != 'Grade Level':
                        category_loadings[category] = -category_loadings[category]
        
        # Scale to 0-100
        weights = {}  # Initialize weights dictionary
        min_loading = min(category_loadings.values())
        max_loading = max(category_loadings.values())
        for category in category_loadings:
            weights[category] = 100 * (category_loadings[category] - min_loading) / (max_loading - min_loading)
        
        # Round weights to nearest whole number for clarity
        weights = {k: round(v) for k, v in weights.items()}
        
        # Ensure all categories have weights (use defaults for any missing)
        default_weights = {
            'Developing': 100,
            'Transitioning': 100, 
            'Higher Emergent': 100,
            'Lower Emergent': 100,
            'Grade Level': 100
        }
        
        for category in default_weights:
            if category not in weights:
                weights[category] = default_weights[category]
        
        print("PCA-derived weights based on valid schools:")
        for category in categories:
            if category in weights:
                print(f"  {category}: {weights[category]}")
        
        return weights
    def get_pca_components_info(self):
        """
        Create a DataFrame of PCA components with proper column names,
        showing the loadings of each feature on the principal components.
        
        Returns
        -------
        pandas.DataFrame
            DataFrame containing PCA components with feature names as columns
        """
        # Check if PCA model exists
        if self.component_model is None:
            print("Error: No PCA model available. Run optimize_weights_from_pca first.")
            return None
        
        # Get the components
        components = self.component_model.components_
        
        # Metadata columns to exclude
        metadata_cols = ['School Name', 'Region', 'Division', 'District']
        
        # Try to reconstruct the feature set used in PCA
        if self.combined_percentage_data is not None and 'EoSY' in self.combined_percentage_data:
            # Define the reading profile categories
            categories = ['Developing', 'Transitioning', 'Higher Emergent', 'Lower Emergent', 'Grade Level']
            
            # Extract reading profile columns
            profile_columns = []
            for category in categories:
                cols = [col for col in self.combined_percentage_data['EoSY'].columns 
                      if category in col and col not in metadata_cols]
                profile_columns.extend(cols)
        else:
            print("Warning: No percentage data available. Using generic column names.")
            profile_columns = [f"Feature_{i}" for i in range(components.shape[1])]
        
        # Check if column count matches component dimensions
        if len(profile_columns) != components.shape[1]:
            print(f"Warning: Column count mismatch. PCA has {components.shape[1]} features, but {len(profile_columns)} columns found.")
            print("This may be due to missing values being dropped during PCA.")
            
            # Either trim or extend the column list
            if len(profile_columns) > components.shape[1]:
                profile_columns = profile_columns[:components.shape[1]]
            else:
                profile_columns = profile_columns + [f"Unknown_{i}" for i in range(components.shape[1] - len(profile_columns))]
        
        # Create DataFrame
        components_df = pd.DataFrame(components, columns=profile_columns)
        
        # Print summary of the weights
        print("=== PCA Component Analysis ===")
        print(f"Number of components: {components.shape[0]}")
        print(f"Number of features: {components.shape[1]}")
        
        if components.shape[0] > 0:
            print("\nComponent 1 Loadings (Top 5 highest absolute value):")
            top_abs = components_df.iloc[0].abs().sort_values(ascending=False).head(5)
            top_indices = top_abs.index
            
            for feature in top_indices:
                loading = components_df.iloc[0][feature]
                print(f"  {feature}: {loading:.4f}")
            
            # Map between loadings and reading profile categories
            if len(components_df.columns) > 0:
                category_loadings = {}
                for category in categories:
                    category_cols = [col for col in components_df.columns if category in col]
                    if category_cols:
                        avg_loading = components_df.iloc[0][category_cols].mean()
                        category_loadings[category] = avg_loading
                
                if category_loadings:
                    print("\nAverage Component 1 Loadings by Category:")
                    for category, loading in sorted(category_loadings.items(), key=lambda x: abs(x[1]), reverse=True):
                        print(f"  {category}: {loading:.4f}")
        
        # Print explained variance if available
        if hasattr(self.component_model, 'explained_variance_ratio_'):
            print(f"\nExplained variance ratio: {self.component_model.explained_variance_ratio_[0]:.4f}")
        
        return components_df

# Example usage
if __name__ == "__main__":
    # Initialize the CRLA analysis class
    crla_analyzer = CRLAv2()
    
    # Load assessment data
    bosy_data, eosy_data = crla_analyzer.load_assessment_data()
    
    # Extract column structures
    identifier_columns, grade_columns_dict = crla_analyzer.extract_column_structures(bosy_data)
    
    # Create school identifier table
    school_identifiers = crla_analyzer.create_school_identifier_table(
        identifier_columns, 
        assessment_dataframes=[bosy_data, eosy_data]
    )
    
    # Create grade-specific data tables
    grade_tables = crla_analyzer.create_grade_data_tables(
        [bosy_data, eosy_data],
        school_identifiers,
        grade_columns_dict
    )
    
    # Calculate raw counts and percentages
    processed_tables = crla_analyzer.calculate_raw_and_percentage_data(
        grade_tables, 
        groupby_column="School ID"
    )
    
    # Extract raw count dataframes for both periods
    bosy_raw_dataframes, eosy_raw_dataframes = crla_analyzer.extract_data_by_period(
        processed_tables, 
        data_type='raw'
    )
    
    # Combine raw count data
    combined_raw_data = crla_analyzer.combine_grade_data(
        bosy_raw_dataframes,
        eosy_raw_dataframes,
        school_identifiers
    )
    
    # Extract percentage dataframes for both periods
    bosy_percentage_dataframes, eosy_percentage_dataframes = crla_analyzer.extract_data_by_period(
        processed_tables, 
        data_type='percentages'
    )
    
    # Combine percentage data
    combined_percentage_data = crla_analyzer.combine_grade_data(
        bosy_percentage_dataframes,
        eosy_percentage_dataframes,
        school_identifiers
    )
    
    # Analyze reading performance with default weights
    # This will also store the data in the class instance
    default_analysis = crla_analyzer.analyze_reading_performance(
        processed_tables,
        combined_raw_data,
        combined_percentage_data
    )
    
    # Define custom weights (optional)
    custom_weights = {
        'Developing': 100,
        'Transitioning': 100,
        'Higher Emergent': 100,
        'Lower Emergent': 100,
        'Grade Level': 100
    }
    
    # Analyze reading performance with custom weights
    custom_analysis = crla_analyzer.analyze_reading_performance(
        processed_tables,
        combined_raw_data,
        combined_percentage_data,
        custom_weights
    )
    
    # Generate PCA-optimized weights (will use stored validation data)
    pca_weights = crla_analyzer.optimize_weights_from_pca()
    
    # Analyze reading performance with PCA-derived weights
    pca_analysis = crla_analyzer.analyze_reading_performance(
        processed_tables,
        combined_raw_data,
        combined_percentage_data,
        pca_weights
    )
    
    # Print data quality summary
    validation = default_analysis['validation']
    valid_count = validation['valid_for_progress'].sum()
    total_count = len(validation)
    
    print("=== CRLA Data Quality Summary ===")
    print(f"Total schools: {total_count}")
    print(f"Schools with BoSY data only: {(validation['has_bosy_data'] & ~validation['has_eosy_data']).sum()}")
    print(f"Schools with EoSY data only: {(~validation['has_bosy_data'] & validation['has_eosy_data']).sum()}")
    
    if 'count_mismatch' in validation.columns:
        print(f"Schools with significant student count differences: {validation['count_mismatch'].sum()}")
    
    print(f"Schools valid for progress analysis: {valid_count} ({valid_count/total_count:.1%})")
    
    # Get performance results using different weight approaches
    results_default = default_analysis['results']
    results_custom = custom_analysis['results']
    results_pca = pca_analysis['results']
    
    # Compare performance across different weight approaches
    print("\n=== Performance Comparison (Valid Schools Only) ===")
    valid_schools = validation[validation['valid_for_progress']].index
    
    print(f"Default weights - Avg Performance: {results_default.loc[valid_schools, 'EoSY Performance'].mean():.2f}")
    print(f"Custom weights - Avg Performance: {results_custom.loc[valid_schools, 'EoSY Performance'].mean():.2f}")
    print(f"PCA weights - Avg Performance: {results_pca.loc[valid_schools, 'EoSY Performance'].mean():.2f}")
    
    print("\n=== Progress Score Comparison (Valid Schools Only) ===")
    print(f"Default weights - Avg Progress: {results_default.loc[valid_schools, 'Progress Score'].mean():.2f}")
    print(f"Custom weights - Avg Progress: {results_custom.loc[valid_schools, 'Progress Score'].mean():.2f}")
    print(f"PCA weights - Avg Progress: {results_pca.loc[valid_schools, 'Progress Score'].mean():.2f}")
    
    # Print top performing schools using PCA weights
    print("\n=== Top 5 Schools by EoSY Performance (PCA Weights) ===")
    top_performing = results_pca.sort_values('EoSY Performance', ascending=False).head(5)
    for idx, row in top_performing.iterrows():
        print(f"School ID: {idx}")
        print(f"  School Name: {row['School Name']}")
        print(f"  Region: {row['Region']}")
        print(f"  Performance Score: {row['EoSY Performance']:.2f}")
        print()
    
    # Print most improved schools using PCA weights
    print("=== Top 5 Schools by Progress (PCA Weights, Valid Schools Only) ===")
    valid_schools_pca = results_pca[results_pca['Valid for Progress Analysis']]
    top_progress = valid_schools_pca.sort_values('Progress Score', ascending=False).head(5)
    for idx, row in top_progress.iterrows():
        print(f"School ID: {idx}")
        print(f"  School Name: {row['School Name']}")
        print(f"  Region: {row['Region']}")
        print(f"  Progress Score: {row['Progress Score']:.2f}")
        print(f"  BoSY to EoSY Change: {row['BoSY Performance']:.2f} → {row['EoSY Performance']:.2f}")
        print()
    
    # Distribution of reading levels at EoSY
    print("=== Overall Reading Profile Distribution (EoSY) ===")
    category_columns = ['EoSY Developing %', 'EoSY Transitioning %', 
                        'EoSY Higher Emergent %', 'EoSY Lower Emergent %']
    
    if all(col in results_pca.columns for col in category_columns):
        avg_distribution = results_pca[category_columns].mean()
        for category, value in avg_distribution.items():
            print(f"  {category}: {value:.1f}%")
    
    print("\nAnalysis complete!")