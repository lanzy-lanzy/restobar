from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .models import Reservation

@login_required
def reservation_feedback(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id, user=request.user)

    if request.method == 'POST':
        rating = request.POST.get('rating')
        comments = request.POST.get('comments')

        # Save feedback to reservation (add fields or adjust as needed)
        reservation.feedback = {
            'rating': rating,
            'comments': comments
        }  # This assumes a JSONField or similar; adjust for your model
        reservation.save()
        messages.success(request, 'Thank you for your feedback!')
        return redirect('my_reservations')

    return render(request, 'reservations/reservation_feedback_form.html', {'reservation': reservation})
