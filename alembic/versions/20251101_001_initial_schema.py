"""Initial schema with all tables

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-11-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # Create meetings table
    op.create_table(
        'meetings',
        sa.Column('meeting_id', sa.String(255), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('recording_url', sa.String(1000), nullable=True),
        sa.Column('recording_drive_id', sa.String(255), nullable=True),
        sa.Column('status', sa.Enum('detected', 'downloading', 'transcribing', 'uploading', 'completed', 'failed', 'skipped', name='meetingstatus'), nullable=False, server_default='detected'),
        sa.Column('project_name', sa.String(100), nullable=False, server_default='GERAL'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('duration_minutes > 0', name='duration_positive'),
        sa.CheckConstraint('duration_minutes <= 180', name='duration_max_3_hours'),
    )

    # Create indexes for meetings
    op.create_index('idx_meeting_status', 'meetings', ['status'])
    op.create_index('idx_meeting_end_time', 'meetings', ['end_time'])
    op.create_index('idx_meeting_project', 'meetings', ['project_name'])

    # Create transcripts table
    op.create_table(
        'transcripts',
        sa.Column('transcript_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('meeting_id', sa.String(255), sa.ForeignKey('meetings.meeting_id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('full_text', sa.Text(), nullable=False),
        sa.Column('markdown_text', sa.Text(), nullable=False),
        sa.Column('word_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('speaker_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('drive_file_id', sa.String(255), nullable=True),
        sa.Column('drive_folder_id', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('word_count >= 0', name='word_count_non_negative'),
        sa.CheckConstraint('speaker_count > 0', name='speaker_count_positive'),
    )

    # Create participants table
    op.create_table(
        'participants',
        sa.Column('participant_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('meeting_id', sa.String(255), sa.ForeignKey('meetings.meeting_id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False, server_default='Unknown Participant'),
        sa.Column('email', sa.String(320), nullable=True),
        sa.Column('speaker_id', sa.String(50), nullable=True),
        sa.Column('attendance_duration_minutes', sa.Integer(), nullable=True),
    )

    # Create indexes for participants
    op.create_index('idx_participant_meeting', 'participants', ['meeting_id'])
    op.create_index('idx_participant_email', 'participants', ['email'])

    # Create projects table
    op.create_table(
        'projects',
        sa.Column('project_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False),
        sa.Column('drive_folder_id', sa.String(255), unique=True, nullable=False),
        sa.Column('classification_rules', sa.JSON(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    # Create processing_jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('job_id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('meeting_id', sa.String(255), sa.ForeignKey('meetings.meeting_id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='jobstatus'), nullable=False, server_default='pending'),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.CheckConstraint('retry_count >= 0', name='retry_count_non_negative'),
        sa.CheckConstraint('retry_count <= 3', name='retry_count_max_3'),
    )

    # Create indexes for processing_jobs
    op.create_index('idx_job_status', 'processing_jobs', ['status'])
    op.create_index('idx_job_next_retry', 'processing_jobs', ['next_retry_at'])
    op.create_index('idx_job_meeting', 'processing_jobs', ['meeting_id'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('processing_jobs')
    op.drop_table('projects')
    op.drop_table('participants')
    op.drop_table('transcripts')
    op.drop_table('meetings')
