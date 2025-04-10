import streamlit as st
from config import DB_URL, MOS_ATTRIBUTES
from database import get_rated_samples, add_mos_rating, get_multiple_random_samples, get_audio_path


def show_mos_evaluation():
    """Main function to display MOS evaluation interface"""
    st.title("MOS Evaluation")
    
    # Initialize session states
    if "mos_started" not in st.session_state:
        st.session_state.mos_started = False
    
    # Handle starting evaluation or continue existing one
    if not st.session_state.mos_started:
        handle_start_evaluation()
        return
    
    # Load or check samples
    samples = load_samples()
    if not samples:
        st.info("No samples available for evaluation.")
        return
    
    # Display samples grid
    display_samples_grid(samples)
    
    # Show progress and navigation
    show_progress_and_navigation(samples)

def handle_start_evaluation():
    """Handle the evaluation start screen"""
    st.write("Click the start button to get random samples for evaluation")
    rated_samples = get_rated_samples(DB_URL, st.session_state.user_id)
    
    if rated_samples:
        st.info(f"You have previously rated {len(rated_samples)} samples.")
    
    if st.button("Start Evaluation", use_container_width=True):
        st.session_state.mos_started = True
        
        # Get samples excluding already rated ones
        rated_samples = get_rated_samples(DB_URL, st.session_state.user_id)
        samples = get_multiple_random_samples(DB_URL, count=10, max_per_model=5, exclude_ids=rated_samples)
        
        if samples:
            st.session_state.mos_samples = samples
            st.session_state.rated_samples = set()
        else:
            st.warning("No unrated samples remaining!")
        st.rerun()

def load_samples():
    """Load samples or initialize if needed"""
    if "mos_samples" not in st.session_state:
        rated_samples = get_rated_samples(DB_URL, st.session_state.user_id)
        samples = get_multiple_random_samples(DB_URL, count=10, max_per_model=5, exclude_ids=rated_samples)
        if samples:
            st.session_state.mos_samples = samples
            st.session_state.rated_samples = set()
    
    return st.session_state.mos_samples

def display_samples_grid(samples):
    """Display the grid of samples"""
    sample_index = 0
    for row in range(5):
        if sample_index >= len(samples):
            break
            
        col1, col2 = st.columns(2)
        
        # First sample
        with col1:
            if sample_index < len(samples):
                display_sample(samples[sample_index], sample_index)
                sample_index += 1
        
        # Second sample
        with col2:
            if sample_index < len(samples):
                display_sample(samples[sample_index], sample_index)
                sample_index += 1

def display_sample(sample, sample_index):
    """Display a single sample with rating functionality"""
    sample_id = sample['sample_id']
    
    st.write(f"**Text:** {sample['text']}")
    st.audio(get_audio_path(sample['audio_url']), format='audio/wav')
    
    # Button changes color if already rated
    button_type = "secondary" if sample_id in st.session_state.rated_samples else "primary"
    button_text = "✓ Rated" if sample_id in st.session_state.rated_samples else "Rate"
    
    # Only show rating form if this specific button is clicked
    if st.button(button_text, key=f"rate_btn_{sample_id}", 
               type=button_type, use_container_width=True):
        st.session_state.current_rating_sample_id = sample_id
        st.session_state.current_rating_sample_index = sample_index
    
    # Show rating form within an expander
    if st.session_state.get('current_rating_sample_id') == sample_id:
        with st.expander("Rating Form", expanded=True):
            show_rating_form( sample_id)

def show_rating_form(sample_id):
    """Display and handle the rating form for a sample"""
    with st.form(f"mos_form_{sample_id}"):
        ratings = {}
        for attr in MOS_ATTRIBUTES:
            ratings[attr['id']] = st.slider(
                f"{attr['label']} - {attr['description']}",
                1.0, 5.0, 3.0, 0.5
            )
        
        # Form buttons
        col_submit, col_cancel = st.columns([1, 1])
        with col_submit:
            submitted = st.form_submit_button("Submit Rating", use_container_width=True)
        with col_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)
        
        # Handle submission
        if submitted:
            handle_rating_submission(sample_id, ratings)
        
        # Handle cancellation
        if cancelled:
            clear_current_rating()
            st.rerun()

def handle_rating_submission(sample_id, ratings):
    """Process the rating submission"""
    # Add null value for speaker_similarity
    ratings["speaker_similarity"] = None
    
    # Save rating
    rating_id = add_mos_rating(
        DB_URL, sample_id, 
        st.session_state.user_id, ratings
    )
    
    if rating_id:
        # Mark as rated
        st.session_state.rated_samples.add(sample_id)
        # Clear current rating sample
        clear_current_rating()
        st.success("Rating has been recorded!")
        st.rerun()
    else:
        st.error("An error occurred while saving the rating.")

def clear_current_rating():
    """Clear current rating session variables"""
    if 'current_rating_sample_id' in st.session_state:
        del st.session_state.current_rating_sample_id
    if 'current_rating_sample_index' in st.session_state:
        del st.session_state.current_rating_sample_index

def show_progress_and_navigation(samples):
    """Show progress bar and navigation buttons"""
    # Progress indicator
    st.progress(len(st.session_state.rated_samples) / len(samples))
    st.write(f"Rated: {len(st.session_state.rated_samples)}/{len(samples)}")
    
    # Navigation buttons
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Get New Samples", use_container_width=True):
            reset_evaluation()
            st.rerun()
    
    with col2:
        if len(st.session_state.rated_samples) == len(samples):
            st.success("You have completed all samples!")

def reset_evaluation():
    """Reset the evaluation state"""
    st.session_state.mos_started = False
    for key in ['mos_samples', 'rated_samples', 'current_rating_sample_id', 'current_rating_sample_index']:
        if key in st.session_state:
            del st.session_state[key]