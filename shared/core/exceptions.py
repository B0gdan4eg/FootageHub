"""
Custom exceptions for FootageHub.

This module defines all custom exceptions used across the application.
"""


class FootageHubException(Exception):
    """Base exception for all FootageHub errors."""


# ==================== USER EXCEPTIONS ====================


class UserException(FootageHubException):
    """Base exception for user-related errors."""


class UserNotFoundError(UserException):
    """Raised when a user is not found."""


# Aliases for backwards compatibility
UserNotFoundException = UserNotFoundError


class UserAlreadyExistsError(UserException):
    """Raised when trying to create a user that already exists."""


# ==================== CREDIT EXCEPTIONS ====================


class CreditException(FootageHubException):
    """Base exception for credit-related errors."""


class InsufficientCreditsError(CreditException):
    """Raised when user doesn't have enough credits."""


class InsufficientAICreditsError(CreditException):
    """Raised when user doesn't have enough AI credits."""


# ==================== BONUS EXCEPTIONS ====================


class BonusException(FootageHubException):
    """Base exception for bonus-related errors."""


class BonusNotFoundError(BonusException):
    """Raised when a bonus type is not found."""


class BonusAlreadyClaimedError(BonusException):
    """Raised when user tries to claim a bonus they already have."""


class BonusConditionNotMetError(BonusException):
    """Raised when bonus conditions are not met."""


class BonusExpiredError(BonusException):
    """Raised when trying to use an expired bonus."""


# ==================== SUBSCRIPTION EXCEPTIONS ====================


class SubscriptionException(FootageHubException):
    """Base exception for subscription-related errors."""


class SubscriptionRequiredError(SubscriptionException):
    """Raised when an action requires an active subscription."""


class SubscriptionExpiredError(SubscriptionException):
    """Raised when subscription has expired."""


class SubscriptionLimitReachedError(SubscriptionException):
    """Raised when subscription download limit is reached."""


# ==================== DOWNLOAD EXCEPTIONS ====================


class DownloadException(FootageHubException):
    """Base exception for download-related errors."""


class InvalidUrlError(DownloadException):
    """Raised when URL is invalid or not supported."""


class DownloadFailedError(DownloadException):
    """Raised when download fails."""


# ==================== AI EXCEPTIONS ====================


class AIException(FootageHubException):
    """Base exception for AI-related errors."""


class AIProviderError(AIException):
    """Raised when AI provider returns an error."""


class AIGenerationFailedError(AIException):
    """Raised when AI generation fails."""


class AIGenerationTimeoutError(AIException):
    """Raised when AI generation times out."""


# ==================== REFERRAL EXCEPTIONS ====================


class ReferralException(FootageHubException):
    """Base exception for referral-related errors."""


class InvalidReferralCodeError(ReferralException):
    """Raised when referral code is invalid."""


class SelfReferralError(ReferralException):
    """Raised when user tries to refer themselves."""
