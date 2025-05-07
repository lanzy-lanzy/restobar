from django.shortcuts import render

def test_static(request):
    """Test page for static files"""
    return render(request, 'test_static.html')
