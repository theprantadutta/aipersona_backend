"""Usage tracking API endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from datetime import date, timedelta

from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.usage_service import UsageService
from app.schemas.usage import (
    CurrentUsageResponse,
    UsageHistoryResponse,
    UsageAnalyticsResponse,
    ExportUsageRequest
)

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/current", response_model=CurrentUsageResponse)
def get_current_usage(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current usage stats for the authenticated user

    Returns:
    - Messages used today vs limit
    - Personas created vs limit
    - Storage used
    - API calls and tokens used
    - Last reset time
    - Premium status

    Free tier limits:
    - 10 messages per day
    - 2 personas
    - 100MB storage

    Premium tier: Unlimited
    """
    try:
        service = UsageService(db)
        usage_data = service.get_current_usage(str(current_user.id))

        return CurrentUsageResponse(**usage_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching current usage: {str(e)}"
        )


@router.get("/history", response_model=UsageHistoryResponse)
def get_usage_history(
    start_date: date = Query(..., description="Start date for history (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date for history (YYYY-MM-DD)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get historical usage data for a date range

    - **start_date**: Start date (inclusive)
    - **end_date**: End date (inclusive)

    Returns daily breakdown of:
    - Messages sent
    - API calls made
    - Tokens consumed

    Maximum range: 90 days
    """
    try:
        # Validate date range
        if end_date < start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date"
            )

        if (end_date - start_date).days > 90:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum date range is 90 days"
            )

        service = UsageService(db)
        history_data = service.get_usage_history(
            user_id=str(current_user.id),
            start_date=start_date,
            end_date=end_date
        )

        return UsageHistoryResponse(**history_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching usage history: {str(e)}"
        )


@router.get("/analytics", response_model=UsageAnalyticsResponse)
def get_usage_analytics(
    days: int = Query(30, ge=7, le=90, description="Number of days to analyze"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get advanced usage analytics and insights

    - **days**: Number of days to analyze (7-90, default: 30)

    Returns:
    - Current usage stats
    - Daily average usage
    - Peak usage day
    - Usage trend (increasing/decreasing/stable)
    - Usage percentage (for free tier)
    - Predictions and recommendations
    """
    try:
        service = UsageService(db)
        analytics_data = service.get_usage_analytics(
            user_id=str(current_user.id),
            days=days
        )

        return UsageAnalyticsResponse(**analytics_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching usage analytics: {str(e)}"
        )


@router.post("/export")
def export_usage_data(
    export_request: ExportUsageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export usage data for a date range

    - **start_date**: Start date (YYYY-MM-DD)
    - **end_date**: End date (YYYY-MM-DD)
    - **format**: Export format (json or csv)
    - **include_details**: Include daily breakdown

    Returns the usage data in the requested format
    Maximum range: 365 days
    """
    try:
        # Validate date range
        if export_request.end_date < export_request.start_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="end_date must be after start_date"
            )

        if (export_request.end_date - export_request.start_date).days > 365:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum export range is 365 days"
            )

        service = UsageService(db)
        export_data = service.export_usage_data(
            user_id=str(current_user.id),
            start_date=export_request.start_date,
            end_date=export_request.end_date,
            format=export_request.format,
            include_details=export_request.include_details
        )

        return JSONResponse(content=export_data)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error exporting usage data: {str(e)}"
        )
