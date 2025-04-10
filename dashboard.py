import streamlit as st
import pandas as pd
import numpy as np
from config import DB_URL
from database import get_ab_results, get_all_mos_data
import plotly.express as px

def show_results():
    """Display evaluation results with simplified visualizations"""
    if not st.session_state.is_admin:
        st.warning("You don't have permission to view this page.")
        return
    
    st.title("Evaluation Results (Admin)")

    tab1, tab2 = st.tabs(["MOS", "A/B Tests"])
    
    with tab1:
        show_mos_results_simplified()
    
    with tab2:
        show_ab_results_simplified()

def show_mos_results_simplified():
    """Display MOS results with side-by-side bars for all metrics and models in one chart"""
    # Get all raw data
    raw_data = get_all_mos_data(DB_URL)
    
    if not raw_data or len(raw_data) == 0:
        st.info("No MOS evaluation data available")
        return
    
    df_raw = pd.DataFrame(raw_data)
    
    # Handle column names if needed
    if isinstance(df_raw.columns[0], int):
        column_names = ['rating_id', 'sample_id', 'user_id', 
                       'naturalness', 'intelligibility', 'pronunciation', 
                       'prosody', 'speaker_similarity', 'overall_rating',
                       'created_at', 'model_name', 'username']
        
        if len(column_names) > len(df_raw.columns):
            column_names = column_names[:len(df_raw.columns)]
            
        df_raw.columns = column_names
    
    if 'model_name' not in df_raw.columns:
        st.error("Column 'model_name' does not exist in the data.")
        return

    # Setup sidebar
    st.sidebar.header("MOS Display Options")
    
    # Filter by model
    available_models = sorted(df_raw['model_name'].unique())
    selected_models = st.sidebar.multiselect(
        "Select models", 
        options=available_models,
        default=available_models
    )
    
    # Define metrics
    available_metrics = [
        ('naturalness', 'Naturalness'), 
        ('intelligibility', 'Intelligibility'),
        ('pronunciation', 'Pronunciation'), 
        ('prosody', 'Prosody'),
        ('speaker_similarity', 'Speaker Similarity'), 
        ('overall_rating', 'Overall')
    ]
    
    selected_metrics = st.sidebar.multiselect(
        "Evaluation Metrics",
        options=[m[0] for m in available_metrics],
        default=['naturalness', 'overall_rating'],
        format_func=lambda x: next((m[1] for m in available_metrics if m[0] == x), x)
    )
    
    # Apply filters
    filtered_df = df_raw.copy()
    if selected_models:
        filtered_df = filtered_df[filtered_df['model_name'].isin(selected_models)]
    
    # Aggregate data
    agg_functions = {metric: 'mean' for metric in selected_metrics}
    if 'rating_id' in filtered_df.columns:
        agg_functions['rating_id'] = 'count'
    
    agg_df = filtered_df.groupby('model_name').agg(agg_functions).reset_index()
    
    if 'rating_id' in agg_df.columns:
        agg_df.rename(columns={'rating_id': 'total_ratings'}, inplace=True)
    
    # Visualize data
    if len(agg_df) > 0:
        st.subheader("MOS Evaluation Results")
        
        # Get metric display names
        metric_names = {m[0]: m[1] for m in available_metrics}
        
        # Làm đơn giản với Streamlit's native charts - hiển thị từng metric
        for metric in selected_metrics:
            metric_display = metric_names[metric]
            st.subheader(metric_display)
            
            # Tạo DataFrame có index là model_name và giá trị là metric
            chart_df = agg_df.set_index('model_name')[metric].sort_values(ascending=False)
            
            # Hiển thị bar chart
            st.bar_chart(chart_df)
            
        # Hiển thị bảng dữ liệu tổng hợp
        st.subheader("Summary Table")
        display_df = agg_df.set_index('model_name')
        st.dataframe(display_df[selected_metrics].rename(columns=metric_names).round(2))
        
        # Tùy chọn tải xuống
        csv = agg_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV Data",
            data=csv,
            file_name='mos_results.csv',
            mime='text/csv',
        )
    else:
        st.warning("No data matches the selected filters")
        
def show_ab_results_simplified():
    """Display A/B test results with simpler visualizations"""
    ab_data = get_ab_results(DB_URL)
    if not ab_data:
        st.info("No A/B evaluation data available")
        return
        
    df = pd.DataFrame(ab_data)
    st.subheader("A/B Comparison Results")
    
    # Create a summary bar chart for all comparisons
    if len(df) > 0:
        st.subheader("Overall Comparison Results")
        
        # Create dataframe for visualization
        chart_data = []
        for _, row in df.iterrows():
            model_pair = f"{row['model_a']} vs {row['model_b']}"
            total = row['total']
            
            # Calculate percentages
            a_percent = (row['a_wins'] / total) * 100
            b_percent = (row['b_wins'] / total) * 100
            tie_percent = ((total - row['a_wins'] - row['b_wins']) / total) * 100 if 'ties' in row else 0
            
            chart_data.append({
                'Pair': model_pair,
                'Model A wins (%)': a_percent,
                'Model B wins (%)': b_percent,
                'Ties (%)': tie_percent
            })
        
        summary_df = pd.DataFrame(chart_data)
        
        # Plot with Streamlit's bar chart
        chart_df = summary_df.set_index('Pair')
        st.bar_chart(chart_df)
    
    # Detailed results for each pair
    for idx, row in df.iterrows():
        # Calculate metrics with ties
        total = row['total']
        ties = row.get('ties', 0)
        total_decisive = row['a_wins'] + row['b_wins']
        tie_ratio = (ties / total) * 100 if total > 0 else 0
        
        # Display basic metrics
        col1, col2, col3 = st.columns([10, 1, 10])
        with col1:
            st.metric(row['model_a'], f"{row['a_wins']} wins")
        with col2:
            st.write("vs")
        with col3:
            st.metric(row['model_b'], f"{row['b_wins']} wins")
        
        # Calculate preference ratio (excluding ties)
        if total_decisive > 0:
            preference_ratio = (row['a_wins'] / total_decisive) * 100
            
            # Calculate confidence interval
            z = 1.96  # 95% confidence level
            n = total_decisive
            p = row['a_wins'] / n
            confidence_interval = z * np.sqrt((p * (1 - p) + z * z / (4 * n)) / n) / (1 + z * z / n) * 100
            
            # Format for display
            lower_bound = max(0, preference_ratio - confidence_interval)
            upper_bound = min(100, preference_ratio + confidence_interval)
            
            # Simple visualization with progress bar
            st.caption(f"Preference for {row['model_a']} ({preference_ratio:.1f}%)")
            st.progress(preference_ratio / 100)
            
            st.caption(f"Total comparisons: {total} (Ties: {ties}, {tie_ratio:.1f}%)")
            
            # Simple win/loss/tie chart
            win_loss_data = pd.DataFrame({
                'Result': ['Wins for ' + row['model_a'], 'Wins for ' + row['model_b'], 'Ties'],
                'Count': [row['a_wins'], row['b_wins'], ties]
            }).set_index('Result')
            
            st.bar_chart(win_loss_data)
            
            # Display statistical results
            st.markdown(f"**{row['model_a']} is preferred over {row['model_b']} {preference_ratio:.1f}%, "
                      f"with confidence interval ±{confidence_interval:.1f}% (95% confidence level, excluding ties)**")
            
            # Conclusion based on confidence interval
            conclusion = ""
            if lower_bound > 55:
                conclusion = f"**Conclusion:** {row['model_a']} is better than {row['model_b']}"
            elif lower_bound > 45 and upper_bound > 55:
                conclusion = f"**Conclusion:** {row['model_a']} is equivalent/better than {row['model_b']}"
            elif lower_bound > 45 and upper_bound < 55:
                conclusion = f"**Conclusion:** {row['model_a']} is equivalent to {row['model_b']}"
            elif lower_bound < 45 and upper_bound < 55:
                conclusion = f"**Conclusion:** {row['model_a']} is worse/equivalent to {row['model_b']}"
            elif upper_bound < 45:
                conclusion = f"**Conclusion:** {row['model_a']} is worse than {row['model_b']}"
            else:
                conclusion = "**Conclusion:** Results are inconclusive, more data needed"
            
            if tie_ratio > 30:
                conclusion += f"\n\n**Note:** High tie rate ({tie_ratio:.1f}%) suggests the two models may be similar in quality"
            
            st.markdown(conclusion)
        else:
            st.warning("Not enough data for statistical analysis")
        
        st.divider()