import streamlit as st
from config import DB_PATH, MOS_ATTRIBUTES
from database import get_rated_ab_samples, add_ab_rating, get_ab_test_sample_pairs

def get_audio_path(url):
    """Helper function to get the full path for audio files"""
    import os
    return os.path.join("static", url)

def show_ab_evaluation():
    """Main function to display A/B evaluation interface"""
    st.title("A/B Evaluation")
    
    # Initialize session states
    if "ab_started" not in st.session_state:
        st.session_state.ab_started = False
    
    # Track the current comparison mode
    if "current_comparison_mode" not in st.session_state:
        st.session_state.current_comparison_mode = "Random both models"
    
    # Comparison options
    comparison_mode = st.radio(
        "Comparison mode",
        options=["Random both models", "Select model A, random model B"],
        horizontal=True
    )
    
    # Reset if mode changed
    if comparison_mode != st.session_state.current_comparison_mode:
        st.session_state.ab_started = False
        st.session_state.current_comparison_mode = comparison_mode
        if "ab_samples" in st.session_state:
            del st.session_state.ab_samples
        if "rated_pairs" in st.session_state:
            del st.session_state.rated_pairs
    
    # Allow selection of model A if appropriate mode
    model_a = None
    if comparison_mode == "Select model A, random model B":
        all_models = get_all_models(DB_PATH)
        model_a = st.selectbox("Select model A", options=[m["model_name"] for m in all_models])
    
    # Start button if not started yet
    if not st.session_state.ab_started:
        st.write("Click the start button to get random sample pairs for evaluation")
        rated_pairs = get_rated_ab_samples(DB_PATH, st.session_state.user_id)
        
        if rated_pairs:
            st.info(f"You have previously rated {len(rated_pairs)} sample pairs.")
        
        if st.button("Start Evaluation", use_container_width=True):
            st.session_state.ab_started = True
            
            # Get samples excluding already rated ones
            rated_pairs = get_rated_ab_samples(DB_PATH, st.session_state.user_id)
            sample_pairs = get_ab_test_sample_pairs(
                DB_PATH, 
                count=5, 
                exclude_pairs=rated_pairs,
                model_a=model_a if comparison_mode == "Select model A, random model B" else None
            )
            
            if sample_pairs:
                st.session_state.ab_samples = sample_pairs
                st.session_state.rated_pairs = set()
                # Save the selected model
                st.session_state.selected_model_a = model_a
            else:
                st.warning("No unrated sample pairs remaining!")
            st.experimental_rerun()
        return
    
    # Load or check samples
    sample_pairs = st.session_state.ab_samples if "ab_samples" in st.session_state else None
    if not sample_pairs:
        st.info("No sample pairs available for evaluation.")
        return
    
    # Display sample pairs grid
    display_sample_pairs_grid(sample_pairs)
    
    # Show progress and navigation
    show_progress_and_navigation(sample_pairs)

def get_all_models(db_path):
    """Get all model names from database"""
    from database import execute_query
    return execute_query(db_path, "SELECT model_id, model_name FROM models")

def load_sample_pairs(model_a=None):
    """Load sample pairs or initialize if needed"""
    if "ab_samples" not in st.session_state:
        rated_pairs = get_rated_ab_samples(DB_PATH, st.session_state.user_id)
        sample_pairs = get_ab_test_sample_pairs(DB_PATH, count=5, exclude_pairs=rated_pairs, model_a=model_a)
        if sample_pairs:
            st.session_state.ab_samples = sample_pairs
            st.session_state.rated_pairs = set()
    
    return st.session_state.ab_samples

def display_sample_pairs_grid(sample_pairs):
    """Display the grid of sample pairs"""
    # Create dictionary to track swap state
    if "pair_swapped_states" not in st.session_state:
        st.session_state.pair_swapped_states = {}
    
    for i, pair in enumerate(sample_pairs):
        # Randomize position of A and B
        import random
        pair_id = f"{pair['sample_a_id']}_{pair['sample_b_id']}"
        
        # Only randomize if not already in session state
        if pair_id not in st.session_state.pair_swapped_states:
            st.session_state.pair_swapped_states[pair_id] = random.choice([True, False])
        
        swap_position = st.session_state.pair_swapped_states[pair_id]
        
        st.write(f"**Text:** {pair['text']}")
        
        col1, col2 = st.columns(2)
        
        # First sample
        with col1:
            st.write("**Sample A**")
            if swap_position:
                st.audio(get_audio_path(pair['audio_b_url']), format='audio/wav')
            else:
                st.audio(get_audio_path(pair['audio_a_url']), format='audio/wav')
        
        # Second sample
        with col2:
            st.write("**Sample B**")
            if swap_position:
                st.audio(get_audio_path(pair['audio_a_url']), format='audio/wav')
            else:
                st.audio(get_audio_path(pair['audio_b_url']), format='audio/wav')
        
        # Button changes color if already rated
        button_type = "secondary" if pair_id in st.session_state.rated_pairs else "primary"
        button_text = "✓ Rated" if pair_id in st.session_state.rated_pairs else "Rate this pair"
        
        # Only show rating form if this specific button is clicked
        if st.button(button_text, key=f"rate_btn_{pair_id}", 
                   type=button_type, use_container_width=True):
            st.session_state.current_rating_pair_id = pair_id
            st.session_state.current_rating_pair_index = i
        
        # Show rating form within an expander
        if st.session_state.get('current_rating_pair_id') == pair_id:
            with st.expander("Rating Form", expanded=True):
                show_ab_rating_form(pair, pair_id, swap_position)
        
        st.divider()

def show_ab_rating_form(pair, pair_id, swap_position):
    """Display and handle the rating form for a sample pair"""
    with st.form(f"ab_form_{pair_id}"):
        selected = st.radio(
            "Which sample is better?",
            ["A", "B", "Both are equivalent"],
            horizontal=True
        )
        
        reason = st.text_area("Reason (optional)")
        
        col_submit, col_cancel = st.columns([1, 1])
        with col_submit:
            submitted = st.form_submit_button("Submit Rating", use_container_width=True)
        with col_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)
        
        # Handle submission
        if submitted:
            handle_ab_rating_submission(pair, pair_id, selected, reason, swap_position)
        
        # Handle cancellation
        if cancelled:
            clear_current_rating()
            st.experimental_rerun()

def handle_ab_rating_submission(pair, pair_id, selected, reason, swap_position):
    """Process the AB rating submission"""
    # Map selection
    if swap_position:
        # If positions were swapped, we need to reverse the selection
        if selected == "A":
            selected_value = "B"
        elif selected == "B":
            selected_value = "A"
        else:
            selected_value = "tie"
    else:
        selected_value = "A" if selected == "A" else "B" if selected == "B" else "tie"
    
    # Save rating
    result_id = add_ab_rating(
        DB_PATH, 
        pair['sample_a_id'], 
        pair['sample_b_id'],
        st.session_state.user_id, 
        selected_value, 
        reason, 
    )
    
    if result_id:
        # Mark as rated
        st.session_state.rated_pairs.add(pair_id)
        # Clear current rating
        clear_current_rating()
        st.success("Rating has been recorded!")
        st.experimental_rerun()
    else:
        st.error("An error occurred while saving the rating.")

def clear_current_rating():
    """Clear current rating session variables"""
    if 'current_rating_pair_id' in st.session_state:
        del st.session_state.current_rating_pair_id
    if 'current_rating_pair_index' in st.session_state:
        del st.session_state.current_rating_pair_index

def show_progress_and_navigation(sample_pairs):
    """Show progress bar and navigation buttons"""
    # Progress indicator
    st.progress(len(st.session_state.rated_pairs) / len(sample_pairs))
    st.write(f"Rated: {len(st.session_state.rated_pairs)}/{len(sample_pairs)}")
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get New Sample Pairs", use_container_width=True):
            reset_evaluation()
            st.experimental_rerun()
    
    with col2:
        if len(st.session_state.rated_pairs) == len(sample_pairs):
            st.success("You have completed all sample pairs!")

def reset_evaluation():
    """Reset the evaluation state"""
    st.session_state.ab_started = False
    for key in ['ab_samples', 'rated_pairs', 'current_rating_pair_id', 'current_rating_pair_index']:
        if key in st.session_state:
            del st.session_state[key]