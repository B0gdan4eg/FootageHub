"""
Custom exceptions for FootageHub.

This module defines all custom exceptions used across the application.
"""


class FootageHubException(Exception):
    """Base exception for all FootageHub errors."""

    pass


# ==================== USER EXCEPTIONS ====================


class UserException(FootageHubException):
    """Base exception for user-related errors."""

    pass


class UserNotFoundError(UserException):
    """Raised when a user is not found."""

    pass


# Aliases for backwards compatibility
UserNotFoundException = UserNotFoundError


class UserAlreadyExistsError(UserException):
    """Raised when trying to create a user that already exists."""

    pass


# ==================== CREDIT EXCEPTIONS ====================


class CreditException(FootageHubException):
    """Base exception for credit-related errors."""

    pass


class InsufficientCreditsError(CreditException):
    """Raised when user doesn't have enough credits."""

    pass


class InsufficientAICreditsError(CreditException):
    """Raised when user doesn't have enough AI credits."""

    pass


# ==================== BONUS EXCEPTIONS ====================


class BonusException(FootageHubException):
    """Base exception for bonus-related errors."""

    pass


class BonusNotFoundError(BonusException):
    """Raised when a bonus type is not found."""

    pass


class BonusAlreadyClaimedError(BonusException):
    """Raised when user tries to claim a bonus they already have."""

    pass


class BonusConditionNotMetError(BonusException):
    """Raised when bonus conditions are not met."""

    pass


class BonusExpiredError(BonusException):
    """Raised when trying to use an expired bonus."""

    pass


# ==================== SUBSCRIPTION EXCEPTIONS ====================


class SubscriptionException(FootageHubException):
    """Base exception for subscription-related errors."""

    pass


class SubscriptionRequiredError(SubscriptionException):
    """Raised when an action requires an active subscription."""

    pass


class SubscriptionExpiredError(SubscriptionException):
    """Raised when subscription has expired."""

    pass


class SubscriptionLimitReachedError(SubscriptionException):
    """Raised when subscription download limit is reached."""

    pass


# ==================== DOWNLOAD EXCEPTIONS ====================


class DownloadException(FootageHubException):
    """Base exception for download-related errors."""

    pass


class InvalidUrlError(DownloadException):
    """Raised when URL is invalid or not supported."""

    pass


class DownloadFailedError(DownloadException):
    """Raised when download fails."""

    pass


# ==================== AI EXCEPTIONS ====================


class AIException(FootageHubException):
    """Base exception for AI-related errors."""

    pass


class AIProviderError(AIException):
    """Raised when AI provider returns an error."""

    pass


class AIGenerationFailedError(AIException):
    """Raised when AI generation fails."""

    pass


class AIGenerationTimeoutError(AIException):
    """Raised when AI generation times out."""

    pass


# ==================== REFERRAL EXCEPTIONS ====================


class ReferralException(FootageHubException):
    """Base exception for referral-related errors."""

    pass


class InvalidReferralCodeError(ReferralException):
    """Raised when referral code is invalid."""

    pass


class SelfReferralError(ReferralException):
    """Raised when user tries to refer themselves."""

    pass
